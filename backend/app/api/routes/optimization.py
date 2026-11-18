"""
Optimization API routes (/api/optimization).

This router strictly handles HTTP orchestration, input validation, and persistence.
All Operations Research mathematical formulations reside in app/optimization/.

Data Integrity Guarantees:
- Never modifies original Demand quantities or Warehouse Inventory stock.
- Persists planned Allocations scoped strictly to each new OptimizationRun.
- Historical runs remain immutable when subsequent runs are executed.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.allocation import Allocation
from app.models.demand import Demand
from app.models.hospital import Hospital
from app.models.inventory import Inventory
from app.models.optimization_run import OptimizationRun
from app.models.product import Product
from app.models.road import Road
from app.models.scenario import Scenario
from app.models.warehouse import Warehouse
from app.optimization.linear_programming import (
    NetworkOptimizationInput,
    OptimizationOutcome,
    OptimizationValidationError,
)
from app.optimization.priority import solve_lexicographic_priority_optimization
from app.optimization.transportation import solve_transportation_problem
from app.schemas.optimization import (
    AllocationItem,
    HospitalSummaryItem,
    OptimizationComparisonResponse,
    OptimizationRequest,
    OptimizationResultResponse,
    OptimizationRunSummary,
    PriorityTierSummary,
    ProductSummaryItem,
    StageResultItem,
    UnmetDemandItem,
    WarehouseUtilizationItem,
)
from app.simulation.scenario_engine import DisasterScenarioConfig, apply_disaster_scenario

router = APIRouter(prefix="/api/optimization", tags=["Optimization"])


def _build_formulation_summary(
    outcome: OptimizationOutcome,
    net_input: NetworkOptimizationInput,
) -> dict[str, Any]:
    """Assemble academic explainability metadata describing the solved OR formulation."""
    is_priority = outcome.model_type == "lexicographic_priority"
    crit_tier = next(
        (p for p in outcome.priority_summary if p["priority_level"] == "critical"), None
    )
    high_tier = next(
        (p for p in outcome.priority_summary if p["priority_level"] == "high"), None
    )
    norm_tier = next(
        (p for p in outcome.priority_summary if p["priority_level"] == "normal"), None
    )

    if outcome.solver_status != "Optimal":
        interpretation = (
            f"Solver terminated with status '{outcome.solver_status}'. "
            "No optimal allocation is claimed. Check supply sufficiency, open routes, "
            "or enable unmet-demand slack variables."
        )
    elif is_priority:
        interpretation = (
            f"Sequential 4-stage lexicographic optimization achieved {outcome.fulfillment_percentage:.2f}% "
            f"overall fulfillment ({outcome.total_allocated:,.0f} of {outcome.total_demand:,.0f} requested units) "
            f"at a minimum constrained transport cost of INR {outcome.total_cost:,.2f}. "
            f"Critical tier fulfillment: {crit_tier['fulfillment_pct'] if crit_tier else 100.0:.2f}%, "
            f"High tier: {high_tier['fulfillment_pct'] if high_tier else 100.0:.2f}%, "
            f"Normal tier: {norm_tier['fulfillment_pct'] if norm_tier else 100.0:.2f}%."
        )
    else:
        interpretation = (
            f"Multi-commodity transportation LP achieved {outcome.fulfillment_percentage:.2f}% "
            f"overall fulfillment ({outcome.total_allocated:,.0f} of {outcome.total_demand:,.0f} requested units) "
            f"at the global minimum transport cost of INR {outcome.total_cost:,.2f} without priority-tier constraints. "
            f"Shortages ({outcome.total_unmet_demand:,.0f} units) are absorbed by higher-cost corridors regardless of hospital urgency."
        )

    return {
        "model_title": (
            "4-Stage Lexicographic Priority Shortage Optimization"
            if is_priority
            else "Multi-Commodity Transportation Linear Program"
        ),
        "solver": outcome.solver_name,
        "solver_status": outcome.solver_status,
        "sets": {
            "warehouses_count": len(net_input.warehouses),
            "hospitals_count": len(net_input.hospitals),
            "products_count": len(net_input.products),
            "available_routes_count": sum(
                1
                for wh in net_input.warehouses
                for hosp in net_input.hospitals
                if net_input.route_availability.get((wh, hosp), False)
            ),
        },
        "decision_variables": [
            "x[i,j,k] >= 0 : Planned quantity of product k transported from warehouse i to hospital j",
            "u[j,k] >= 0   : Unmet demand (shortage) of product k at hospital j",
        ],
        "variable_count": outcome.variable_count,
        "constraint_count": outcome.constraint_count,
        "objective_function": (
            "Lexicographic Min: [ F_critical, F_high, F_normal, Sum_{i,j,k} C[i,j,k] * x[i,j,k] ]"
            if is_priority
            else "Min Sum_{j,k} u[j,k], then Min Sum_{i,j,k} C[i,j,k] * x[i,j,k]"
        ),
        "constraints": [
            "Warehouse stock limit: Sum_{j in J} x[i,j,k] <= S[i,k]  (for all i in I, k in K)",
            "Hospital demand balance: Sum_{i in I} x[i,j,k] + u[j,k] = D[j,k]  (for all j in J, k in K)",
            "Route availability: x[i,j,k] = 0 whenever route (i,j) is unavailable (A[i,j] = 0)",
            "Non-negativity: x[i,j,k] >= 0 and u[j,k] >= 0",
        ],
        "priority_sequence": (
            [
                "Stage 1: Minimize normalized unmet-demand fraction for Critical hospitals (F_critical)",
                "Stage 2: Lock F_critical* and minimize High-priority unmet-demand fraction (F_high)",
                "Stage 3: Lock F_critical*, F_high* and minimize Normal-priority unmet-demand fraction (F_normal)",
                "Stage 4: Lock all tier optimums and minimize total transportation cost",
            ]
            if is_priority
            else [
                "Stage 1: Minimize aggregate unmet demand across all hospitals equally",
                "Stage 2: Minimize total transportation cost while preserving maximum fulfillment",
            ]
        ),
        "interpretation": interpretation,
    }


def _build_network_input_from_db(
    db: Session,
    request: OptimizationRequest,
) -> tuple[
    NetworkOptimizationInput,
    dict[str, int],
    dict[str, int],
    dict[str, int],
    dict[str, tuple[str, str]],
]:
    """Assemble and validate canonical NetworkOptimizationInput from persisted SQLAlchemy tables."""
    if request.scenario_id is not None:
        scenario_row = db.get(Scenario, request.scenario_id)
        if not scenario_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Scenario with id {request.scenario_id} does not exist.",
            )

    warehouses = list(db.scalars(select(Warehouse).where(Warehouse.status == "active")).all())
    hospitals = list(db.scalars(select(Hospital).where(Hospital.status == "active")).all())
    products = list(db.scalars(select(Product)).all())

    if request.warehouse_codes:
        requested_wh = set(request.warehouse_codes)
        available_wh = {w.code for w in warehouses}
        unknown_wh = sorted(requested_wh - available_wh)
        if unknown_wh:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown or inactive warehouse code(s): {', '.join(unknown_wh)}",
            )
        warehouses = [w for w in warehouses if w.code in requested_wh]

    if request.hospital_codes:
        requested_h = set(request.hospital_codes)
        available_h = {h.code for h in hospitals}
        unknown_h = sorted(requested_h - available_h)
        if unknown_h:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown or inactive hospital code(s): {', '.join(unknown_h)}",
            )
        hospitals = [h for h in hospitals if h.code in requested_h]

    if request.product_codes:
        requested_p = set(request.product_codes)
        available_p = {p.code for p in products}
        unknown_p = sorted(requested_p - available_p)
        if unknown_p:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown product code(s): {', '.join(unknown_p)}",
            )
        products = [p for p in products if p.code in requested_p]

    if not warehouses or not hospitals or not products:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Optimization requires at least one active warehouse, hospital, and medical product.",
        )

    inventories = list(db.scalars(select(Inventory)).all())
    demands = list(
        db.scalars(
            select(Demand).where(Demand.status.in_(["open", "partially_fulfilled"]))
        ).all()
    )
    roads = list(db.scalars(select(Road)).all())

    wh_id_to_code = {w.id: w.code for w in warehouses}
    hosp_id_to_code = {h.id: h.code for h in hospitals}
    prod_id_to_code = {p.id: p.code for p in products}
    prod_cost_factor = {p.code: p.base_transport_cost_per_km for p in products}
    prod_weights = {p.code: p.unit_weight_kg for p in products}

    supply: dict[tuple[str, str], float] = {}
    for inv in inventories:
        wh_code = wh_id_to_code.get(inv.warehouse_id)
        prod_code = prod_id_to_code.get(inv.product_id)
        if wh_code and prod_code:
            net_available = max(0, inv.quantity_available - inv.quantity_reserved)
            supply[(wh_code, prod_code)] = float(net_available)

    demand_map: dict[tuple[str, str], float] = {}
    for dem in demands:
        hosp_code = hosp_id_to_code.get(dem.hospital_id)
        prod_code = prod_id_to_code.get(dem.product_id)
        if hosp_code and prod_code:
            demand_map[(hosp_code, prod_code)] = (
                demand_map.get((hosp_code, prod_code), 0.0) + float(dem.quantity_requested)
            )

    if sum(demand_map.values()) <= 0.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No open or partially fulfilled demand requests exist for the selected hospitals and products.",
        )

    # Default every warehouse-hospital pair without an explicit Road row to unavailable
    route_availability: dict[tuple[str, str], bool] = {
        (w.code, h.code): False for w in warehouses for h in hospitals
    }
    unit_cost: dict[tuple[str, str, str], float] = {}
    route_code_to_pair: dict[str, tuple[str, str]] = {}
    route_metadata: dict[tuple[str, str], dict[str, Any]] = {}

    for road in roads:
        wh_code = wh_id_to_code.get(road.warehouse_id)
        hosp_code = hosp_id_to_code.get(road.hospital_id)
        if not wh_code or not hosp_code:
            continue
        route_code_to_pair[road.route_code] = (wh_code, hosp_code)
        route_availability[(wh_code, hosp_code)] = (
            bool(road.is_available) if request.enforce_route_availability else True
        )
        route_metadata[(wh_code, hosp_code)] = {
            "route_code": road.route_code,
            "distance_km": road.distance_km,
            "estimated_travel_time_min": road.estimated_travel_time_min,
        }
        for prod_code in prod_id_to_code.values():
            unit_cost[(wh_code, hosp_code, prod_code)] = round(
                road.base_transport_cost_per_unit
                + road.distance_km * prod_cost_factor[prod_code],
                4,
            )

    net_input = NetworkOptimizationInput(
        warehouses=[w.code for w in warehouses],
        hospitals=[h.code for h in hospitals],
        products=[p.code for p in products],
        hospital_priorities={h.code: h.priority_level for h in hospitals},
        supply=supply,
        demand=demand_map,
        unit_cost=unit_cost,
        route_availability=route_availability,
        product_weight_kg=prod_weights,
        warehouse_names={w.code: w.name for w in warehouses},
        hospital_names={h.code: h.name for h in hospitals},
        product_names={p.code: p.name for p in products},
        product_units={p.code: p.unit for p in products},
        route_metadata=route_metadata,
    )

    return (
        net_input,
        {w.code: w.id for w in warehouses},
        {h.code: h.id for h in hospitals},
        {p.code: p.id for p in products},
        route_code_to_pair,
    )


def _execute_and_persist(
    db: Session,
    request: OptimizationRequest,
    forced_model_type: str | None = None,
) -> OptimizationResultResponse:
    """Delegate solving to OR package and record immutable OptimizationRun + planned Allocations."""
    model_type = forced_model_type or request.model_type
    (
        net_input,
        wh_code_to_id,
        hosp_code_to_id,
        prod_code_to_id,
        route_code_to_pair,
    ) = _build_network_input_from_db(db, request)

    # Apply optional disruption parameters via scenario engine
    if (
        request.disabled_warehouse_codes
        or request.closed_route_codes
        or abs(request.demand_multiplier - 1.0) > 1e-6
    ):
        closed_pairs = {
            route_code_to_pair[rc]
            for rc in request.closed_route_codes
            if rc in route_code_to_pair
        }
        scenario_cfg = DisasterScenarioConfig(
            name="ad_hoc_request",
            disabled_warehouses=set(request.disabled_warehouse_codes),
            closed_routes=closed_pairs,
            demand_multiplier=request.demand_multiplier,
        )
        net_input = apply_disaster_scenario(net_input, scenario_cfg)

    try:
        if model_type == "transportation_lp":
            outcome = solve_transportation_problem(
                net_input, allow_unmet_demand=request.allow_unmet_demand
            )
        else:
            outcome = solve_lexicographic_priority_optimization(net_input)
    except OptimizationValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization solver execution failed: {exc}",
        ) from exc

    formulation_summary = _build_formulation_summary(outcome, net_input)
    run_code = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"

    persisted_summary = {
        "solver_name": outcome.solver_name,
        "total_demand": outcome.total_demand,
        "fulfillment_percentage": outcome.fulfillment_percentage,
        "tier_unmet_fractions": outcome.tier_unmet_fractions,
        "priority_summary": outcome.priority_summary,
        "warehouse_utilization": outcome.warehouse_utilization,
        "product_summary": outcome.product_summary,
        "hospital_summary": outcome.hospital_summary,
        "stage_results": outcome.stage_results,
        "unmet_demands": outcome.unmet_demands,
        "allocations_snapshot": outcome.allocations,
        "formulation_summary": formulation_summary,
        "selected_scope": {
            "warehouses": net_input.warehouses,
            "hospitals": net_input.hospitals,
            "products": net_input.products,
        },
    }

    run_record = OptimizationRun(
        run_code=run_code,
        model_type=outcome.model_type,
        scenario_id=request.scenario_id,
        solver_status=outcome.solver_status,
        total_cost=outcome.total_cost,
        total_allocated=outcome.total_allocated,
        total_unmet_demand=outcome.total_unmet_demand,
        execution_time_ms=outcome.execution_time_ms,
        summary_json=persisted_summary,
    )
    db.add(run_record)
    db.flush()

    if outcome.solver_status == "Optimal":
        for alloc in outcome.allocations:
            db.add(
                Allocation(
                    optimization_run_id=run_record.id,
                    warehouse_id=wh_code_to_id[alloc["warehouse_code"]],
                    hospital_id=hosp_code_to_id[alloc["hospital_code"]],
                    product_id=prod_code_to_id[alloc["product_code"]],
                    quantity_allocated=alloc["quantity_allocated"],
                    unmet_quantity=0.0,
                    transport_cost=alloc["transport_cost"],
                )
            )
    db.commit()
    db.refresh(run_record)

    note = (
        "Planned allocations computed dynamically via PuLP CBC. Original warehouse stock and hospital demand records remain unchanged."
        if outcome.solver_status == "Optimal"
        else f"Solver returned status '{outcome.solver_status}'. Review constraints, stock levels, or route availability."
    )

    return OptimizationResultResponse(
        id=run_record.id,
        run_code=run_code,
        executed_at=run_record.created_at,
        model_type=outcome.model_type,
        solver_name=outcome.solver_name,
        solver_status=outcome.solver_status,
        is_planned_allocation=True,
        total_cost=outcome.total_cost,
        total_demand=outcome.total_demand,
        total_allocated=outcome.total_allocated,
        total_unmet_demand=outcome.total_unmet_demand,
        fulfillment_percentage=outcome.fulfillment_percentage,
        tier_unmet_fractions=outcome.tier_unmet_fractions,
        priority_summary=[PriorityTierSummary(**item) for item in outcome.priority_summary],
        warehouse_utilization=[
            WarehouseUtilizationItem(**item) for item in outcome.warehouse_utilization
        ],
        product_summary=[ProductSummaryItem(**item) for item in outcome.product_summary],
        hospital_summary=[HospitalSummaryItem(**item) for item in outcome.hospital_summary],
        stage_results=[StageResultItem(**item) for item in outcome.stage_results],
        execution_time_ms=outcome.execution_time_ms,
        allocations=[AllocationItem(**item) for item in outcome.allocations],
        unmet_demands=[UnmetDemandItem(**item) for item in outcome.unmet_demands],
        formulation_summary=formulation_summary,
        notes=note,
    )


@router.get("/runs", response_model=list[OptimizationRunSummary])
def list_optimization_runs(db: Session = Depends(get_db)) -> list[OptimizationRunSummary]:
    """List historical optimization runs ordered most recent first."""
    stmt = select(OptimizationRun).order_by(OptimizationRun.created_at.desc(), OptimizationRun.id.desc()).limit(50)
    return list(db.scalars(stmt).all())


@router.get("/runs/{run_id}", response_model=OptimizationResultResponse)
def get_optimization_run_detail(
    run_id: int, db: Session = Depends(get_db)
) -> OptimizationResultResponse:
    """Retrieve complete persisted results for a specific historical optimization run."""
    run_record = db.get(OptimizationRun, run_id)
    if not run_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Optimization run with id {run_id} not found.",
        )

    summary = run_record.summary_json or {}
    allocations_data = summary.get("allocations_snapshot")
    if allocations_data is None:
        # Backwards compatibility for Phase 1 runs lacking allocations_snapshot
        wh_map = {w.id: w for w in db.scalars(select(Warehouse)).all()}
        hosp_map = {h.id: h for h in db.scalars(select(Hospital)).all()}
        prod_map = {p.id: p for p in db.scalars(select(Product)).all()}
        rows = list(
            db.scalars(
                select(Allocation).where(Allocation.optimization_run_id == run_record.id)
            ).all()
        )
        allocations_data = []
        for row in rows:
            wh = wh_map.get(row.warehouse_id)
            hosp = hosp_map.get(row.hospital_id)
            prod = prod_map.get(row.product_id)
            unit_cost = (
                round(row.transport_cost / row.quantity_allocated, 4)
                if row.quantity_allocated > 0
                else 0.0
            )
            allocations_data.append(
                {
                    "warehouse_code": wh.code if wh else f"WH-{row.warehouse_id}",
                    "warehouse_name": wh.name if wh else None,
                    "hospital_code": hosp.code if hosp else f"HOSP-{row.hospital_id}",
                    "hospital_name": hosp.name if hosp else None,
                    "hospital_priority": hosp.priority_level if hosp else None,
                    "product_code": prod.code if prod else f"PROD-{row.product_id}",
                    "product_name": prod.name if prod else None,
                    "product_unit": prod.unit if prod else "units",
                    "quantity_allocated": row.quantity_allocated,
                    "unit_cost": unit_cost,
                    "transport_cost": row.transport_cost,
                }
            )

    total_demand = float(
        summary.get("total_demand", run_record.total_allocated + run_record.total_unmet_demand)
    )
    fulfillment_pct = float(
        summary.get(
            "fulfillment_percentage",
            round((run_record.total_allocated / total_demand) * 100.0, 2)
            if total_demand > 0
            else 100.0,
        )
    )

    return OptimizationResultResponse(
        id=run_record.id,
        run_code=run_record.run_code,
        executed_at=run_record.created_at,
        model_type=run_record.model_type,
        solver_name=summary.get("solver_name", "PuLP CBC (COIN-OR Branch and Cut)"),
        solver_status=run_record.solver_status,
        is_planned_allocation=True,
        total_cost=run_record.total_cost,
        total_demand=round(total_demand, 4),
        total_allocated=run_record.total_allocated,
        total_unmet_demand=run_record.total_unmet_demand,
        fulfillment_percentage=fulfillment_pct,
        tier_unmet_fractions=summary.get("tier_unmet_fractions", {}),
        priority_summary=[
            PriorityTierSummary(**item) for item in summary.get("priority_summary", [])
        ],
        warehouse_utilization=[
            WarehouseUtilizationItem(**item)
            for item in summary.get("warehouse_utilization", [])
        ],
        product_summary=[
            ProductSummaryItem(**item) for item in summary.get("product_summary", [])
        ],
        hospital_summary=[
            HospitalSummaryItem(**item) for item in summary.get("hospital_summary", [])
        ],
        stage_results=[StageResultItem(**item) for item in summary.get("stage_results", [])],
        execution_time_ms=run_record.execution_time_ms,
        allocations=[AllocationItem(**item) for item in allocations_data],
        unmet_demands=[UnmetDemandItem(**item) for item in summary.get("unmet_demands", [])],
        formulation_summary=summary.get("formulation_summary", {}),
        notes="Loaded from immutable persisted optimization history.",
    )


@router.get("/latest-allocations")
def get_latest_run_allocations(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Return aggregated allocated quantities per (hospital_id, product_id) from the latest run."""
    latest_run = db.scalar(
        select(OptimizationRun)
        .order_by(OptimizationRun.created_at.desc(), OptimizationRun.id.desc())
        .limit(1)
    )
    if not latest_run:
        return {"run_code": None, "model_type": None, "allocations_by_pair": {}}

    rows = list(
        db.scalars(
            select(Allocation).where(Allocation.optimization_run_id == latest_run.id)
        ).all()
    )
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        key = f"{row.hospital_id}:{row.product_id}"
        totals[key] = round(totals[key] + float(row.quantity_allocated), 4)

    return {
        "run_code": latest_run.run_code,
        "model_type": latest_run.model_type,
        "allocations_by_pair": dict(totals),
    }


@router.post("/transportation", response_model=OptimizationResultResponse)
def run_transportation_optimization(
    request: OptimizationRequest = OptimizationRequest(model_type="transportation_lp"),
    db: Session = Depends(get_db),
) -> OptimizationResultResponse:
    """Execute and persist the multi-commodity transportation LP solver."""
    return _execute_and_persist(db, request, forced_model_type="transportation_lp")


@router.post("/priority", response_model=OptimizationResultResponse)
def run_priority_optimization(
    request: OptimizationRequest = OptimizationRequest(model_type="lexicographic_priority"),
    db: Session = Depends(get_db),
) -> OptimizationResultResponse:
    """Execute and persist the 4-stage lexicographic priority-based shortage optimization solver."""
    return _execute_and_persist(db, request, forced_model_type="lexicographic_priority")


@router.post("/compare", response_model=OptimizationComparisonResponse)
def compare_optimization_models(
    request: OptimizationRequest = OptimizationRequest(),
    db: Session = Depends(get_db),
) -> OptimizationComparisonResponse:
    """
    Execute both Transportation LP and Lexicographic Priority Optimization on the
    exact same network dataset and return structured side-by-side comparison metrics.
    """
    transport_res = _execute_and_persist(db, request, forced_model_type="transportation_lp")
    priority_res = _execute_and_persist(db, request, forced_model_type="lexicographic_priority")

    cost_diff = round(priority_res.total_cost - transport_res.total_cost, 2)
    cost_diff_pct = (
        round((cost_diff / transport_res.total_cost) * 100.0, 2)
        if transport_res.total_cost > 0
        else 0.0
    )

    def _tier_map(res: OptimizationResultResponse) -> dict[str, PriorityTierSummary]:
        return {item.priority_level: item for item in res.priority_summary}

    t_tiers = _tier_map(transport_res)
    p_tiers = _tier_map(priority_res)

    tier_comparison = []
    for tier in ("critical", "high", "normal"):
        t_item = t_tiers.get(tier)
        p_item = p_tiers.get(tier)
        tier_comparison.append(
            {
                "priority_level": tier,
                "demand": t_item.total_demand if t_item else 0.0,
                "transportation_unmet": t_item.total_unmet if t_item else 0.0,
                "priority_unmet": p_item.total_unmet if p_item else 0.0,
                "transportation_fulfillment_pct": t_item.fulfillment_pct if t_item else 100.0,
                "priority_fulfillment_pct": p_item.fulfillment_pct if p_item else 100.0,
                "unmet_reduction": round(
                    (t_item.total_unmet if t_item else 0.0)
                    - (p_item.total_unmet if p_item else 0.0),
                    4,
                ),
            }
        )

    crit_saved = tier_comparison[0]["unmet_reduction"]
    high_saved = tier_comparison[1]["unmet_reduction"]
    explanation = (
        f"Lexicographic Priority Optimization reduced Critical-tier unmet demand by {crit_saved:,.0f} unit(s) "
        f"and High-tier unmet demand by {high_saved:,.0f} unit(s) compared to pure Transportation Cost Optimization, "
        f"with a transportation cost trade-off of INR {cost_diff:+,.2f} ({cost_diff_pct:+.2f}%). "
        "Pure transportation optimization allocates scarce supplies to the lowest-cost corridors regardless of hospital urgency, "
        "whereas lexicographic optimization mathematically protects Critical and High tiers first."
    )

    return OptimizationComparisonResponse(
        transportation=transport_res,
        lexicographic_priority=priority_res,
        comparison_metrics={
            "cost_difference_inr": cost_diff,
            "cost_difference_pct": cost_diff_pct,
            "total_allocated_difference": round(
                priority_res.total_allocated - transport_res.total_allocated, 4
            ),
            "tier_comparison": tier_comparison,
            "explanation": explanation,
        },
    )
