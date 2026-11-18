"""
Optimization API routes (/api/optimization).

This router strictly handles HTTP orchestration and persistence.
All Operations Research mathematical formulations reside in app/optimization/.
"""

from __future__ import annotations

from datetime import datetime, timezone
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
from app.models.warehouse import Warehouse
from app.optimization.linear_programming import NetworkOptimizationInput
from app.optimization.priority import solve_lexicographic_priority_optimization
from app.optimization.transportation import solve_transportation_problem
from app.schemas.optimization import (
    AllocationItem,
    OptimizationRequest,
    OptimizationResultResponse,
    OptimizationRunSummary,
    UnmetDemandItem,
)
from app.simulation.scenario_engine import DisasterScenarioConfig, apply_disaster_scenario

router = APIRouter(prefix="/api/optimization", tags=["Optimization"])


def _build_network_input_from_db(
    db: Session,
    enforce_route_availability: bool = True,
) -> tuple[
    NetworkOptimizationInput,
    dict[str, int],
    dict[str, int],
    dict[str, int],
    dict[str, tuple[str, str]],
]:
    """Assemble canonical NetworkOptimizationInput from persisted SQLAlchemy tables."""
    warehouses = list(db.scalars(select(Warehouse).where(Warehouse.status == "active")).all())
    hospitals = list(db.scalars(select(Hospital).where(Hospital.status == "active")).all())
    products = list(db.scalars(select(Product)).all())
    inventories = list(db.scalars(select(Inventory)).all())
    demands = list(db.scalars(select(Demand).where(Demand.status == "open")).all())
    roads = list(db.scalars(select(Road)).all())

    if not warehouses or not hospitals or not products:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database must contain active warehouses, hospitals, and products before optimizing.",
        )

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

    unit_cost: dict[tuple[str, str, str], float] = {}
    route_availability: dict[tuple[str, str], bool] = {}
    route_code_to_pair: dict[str, tuple[str, str]] = {}

    for road in roads:
        wh_code = wh_id_to_code.get(road.warehouse_id)
        hosp_code = hosp_id_to_code.get(road.hospital_id)
        if not wh_code or not hosp_code:
            continue
        route_code_to_pair[road.route_code] = (wh_code, hosp_code)
        route_availability[(wh_code, hosp_code)] = (
            bool(road.is_available) if enforce_route_availability else True
        )
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
    """Delegate solving to OR package and record OptimizationRun + Allocations."""
    model_type = forced_model_type or request.model_type
    (
        net_input,
        wh_code_to_id,
        hosp_code_to_id,
        prod_code_to_id,
        route_code_to_pair,
    ) = _build_network_input_from_db(db, enforce_route_availability=request.enforce_route_availability)

    # Apply optional ad-hoc disruption parameters via scenario engine
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

    if model_type == "transportation_lp":
        outcome = solve_transportation_problem(net_input, allow_unmet_demand=True)
    else:
        outcome = solve_lexicographic_priority_optimization(net_input)

    run_code = f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
    run_record = OptimizationRun(
        run_code=run_code,
        model_type=outcome.model_type,
        scenario_id=request.scenario_id,
        solver_status=outcome.solver_status,
        total_cost=outcome.total_cost,
        total_allocated=outcome.total_allocated,
        total_unmet_demand=outcome.total_unmet_demand,
        execution_time_ms=outcome.execution_time_ms,
        summary_json={"tier_unmet_fractions": outcome.tier_unmet_fractions},
    )
    db.add(run_record)
    db.flush()

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

    return OptimizationResultResponse(
        run_code=run_code,
        model_type=outcome.model_type,
        solver_status=outcome.solver_status,
        total_cost=outcome.total_cost,
        total_allocated=outcome.total_allocated,
        total_unmet_demand=outcome.total_unmet_demand,
        tier_unmet_fractions=outcome.tier_unmet_fractions,
        execution_time_ms=outcome.execution_time_ms,
        allocations=[AllocationItem(**item) for item in outcome.allocations],
        unmet_demands=[UnmetDemandItem(**item) for item in outcome.unmet_demands],
        notes="Computed dynamically via PuLP CBC solver using current database records.",
    )


@router.get("/runs", response_model=list[OptimizationRunSummary])
def list_optimization_runs(db: Session = Depends(get_db)) -> list[OptimizationRunSummary]:
    """List historical optimization runs ordered most recent first."""
    stmt = select(OptimizationRun).order_by(OptimizationRun.created_at.desc()).limit(50)
    return list(db.scalars(stmt).all())


@router.post("/transportation", response_model=OptimizationResultResponse)
def run_transportation_optimization(
    request: OptimizationRequest = OptimizationRequest(model_type="transportation_lp"),
    db: Session = Depends(get_db),
) -> OptimizationResultResponse:
    """Execute the multi-commodity transportation LP solver."""
    return _execute_and_persist(db, request, forced_model_type="transportation_lp")


@router.post("/priority", response_model=OptimizationResultResponse)
def run_priority_optimization(
    request: OptimizationRequest = OptimizationRequest(model_type="lexicographic_priority"),
    db: Session = Depends(get_db),
) -> OptimizationResultResponse:
    """Execute the 4-stage lexicographic priority-based shortage optimization solver."""
    return _execute_and_persist(db, request, forced_model_type="lexicographic_priority")
