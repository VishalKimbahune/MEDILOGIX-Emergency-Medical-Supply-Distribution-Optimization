"""Performance Analytics API routes (/api/analytics)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.connection import get_db
from app.models.demand import Demand
from app.models.dispatch import DeliveryStop, DispatchPlan, ShipmentLine, VehicleAssignment
from app.models.hospital import Hospital
from app.models.inventory import Inventory
from app.models.optimization_run import OptimizationRun
from app.models.product import Product
from app.models.scenario import Scenario
from app.models.scenario_run import ScenarioRun
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse

router = APIRouter(
    prefix="/api/analytics",
    tags=["Analytics"],
    dependencies=[Depends(require_admin)],
)


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Compute live operational KPIs directly from database records.

    Never returns hardcoded metrics. When no optimization run has been
    executed yet, cost/fulfillment fields explicitly return None.
    """
    total_warehouses = db.scalar(select(func.count(Warehouse.id))) or 0
    total_hospitals = db.scalar(select(func.count(Hospital.id))) or 0
    critical_hospitals = (
        db.scalar(
            select(func.count(Hospital.id)).where(Hospital.priority_level == "critical")
        )
        or 0
    )
    total_available_inventory = (
        db.scalar(select(func.coalesce(func.sum(Inventory.quantity_available), 0))) or 0
    )
    total_storage_capacity = (
        db.scalar(select(func.coalesce(func.sum(Warehouse.storage_capacity_units), 0))) or 0
    )
    total_open_demand = (
        db.scalar(
            select(func.coalesce(func.sum(Demand.quantity_requested), 0)).where(
                Demand.status == "open",
                or_(Demand.approval_status == "approved", Demand.approval_status.is_(None)),
            )
        )
        or 0
    )
    total_partially_fulfilled_demand = (
        db.scalar(
            select(func.coalesce(func.sum(Demand.quantity_requested), 0)).where(
                Demand.status == "partially_fulfilled",
                or_(Demand.approval_status == "approved", Demand.approval_status.is_(None)),
            )
        )
        or 0
    )
    pending_approval_demand_units = (
        db.scalar(
            select(func.coalesce(func.sum(Demand.quantity_requested), 0)).where(
                Demand.status == "pending_approval"
            )
        )
        or 0
    )
    pending_order_approvals_count = (
        db.scalar(
            select(func.count(Demand.id)).where(Demand.status == "pending_approval")
        )
        or 0
    )
    pending_user_approvals_count = (
        db.scalar(
            select(func.count(User.id)).where(User.approval_status == "pending")
        )
        or 0
    )
    total_actionable_demand = int(total_open_demand) + int(total_partially_fulfilled_demand)

    latest_run = db.scalar(
        select(OptimizationRun)
        .order_by(OptimizationRun.created_at.desc(), OptimizationRun.id.desc())
        .limit(1)
    )

    inventory_utilization_pct = (
        round((total_available_inventory / total_storage_capacity) * 100.0, 2)
        if total_storage_capacity > 0
        else 0.0
    )

    fulfillment_pct: float | None = None
    latest_distribution_cost: float | None = None
    latest_run_total_demand: float | None = None
    latest_run_total_allocated: float | None = None
    latest_run_total_unmet: float | None = None
    latest_run_scope: dict[str, Any] | None = None
    if latest_run:
        run_summary = latest_run.summary_json or {}
        denom = float(
            run_summary.get(
                "total_demand", latest_run.total_allocated + latest_run.total_unmet_demand
            )
        )
        fulfillment_pct = (
            round((latest_run.total_allocated / denom) * 100.0, 2) if denom > 0 else 100.0
        )
        latest_distribution_cost = latest_run.total_cost
        latest_run_total_demand = round(denom, 2)
        latest_run_total_allocated = round(latest_run.total_allocated, 2)
        latest_run_total_unmet = round(latest_run.total_unmet_demand, 2)
        latest_run_scope = run_summary.get("selected_scope")

    return {
        "total_warehouses": int(total_warehouses),
        "total_hospitals": int(total_hospitals),
        "critical_hospital_alerts": int(critical_hospitals),
        "available_inventory_units": int(total_available_inventory),
        "total_open_demand_units": int(total_open_demand),
        "total_partially_fulfilled_demand_units": int(total_partially_fulfilled_demand),
        "total_actionable_demand_units": total_actionable_demand,
        "pending_approval_demand_units": int(pending_approval_demand_units),
        "pending_order_approvals_count": int(pending_order_approvals_count),
        "pending_user_approvals_count": int(pending_user_approvals_count),
        "inventory_utilization_pct": inventory_utilization_pct,
        "latest_demand_fulfillment_pct": fulfillment_pct,
        "latest_distribution_cost": latest_distribution_cost,
        "latest_run_code": latest_run.run_code if latest_run else None,
        "latest_run_total_demand": latest_run_total_demand,
        "latest_run_total_allocated": latest_run_total_allocated,
        "latest_run_total_unmet": latest_run_total_unmet,
        "latest_run_scope": latest_run_scope,
        "data_source_note": "Computed live from seeded synthetic simulation tables.",
    }


@router.get("/supply-demand-gap")
def get_supply_demand_gap(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return product-wise aggregate available supply vs. actionable (open + partially fulfilled) demand."""
    products = list(db.scalars(select(Product).order_by(Product.code)).all())
    inventories = list(db.scalars(select(Inventory)).all())
    demands = list(
        db.scalars(
            select(Demand).where(
                Demand.status.in_(["open", "partially_fulfilled"]),
                or_(Demand.approval_status == "approved", Demand.approval_status.is_(None)),
            )
        ).all()
    )

    supply_by_prod: dict[int, int] = defaultdict(int)
    for inv in inventories:
        supply_by_prod[inv.product_id] += max(0, inv.quantity_available - inv.quantity_reserved)

    demand_by_prod: dict[int, int] = defaultdict(int)
    for dem in demands:
        demand_by_prod[dem.product_id] += dem.quantity_requested

    results: list[dict[str, Any]] = []
    for prod in products:
        sup = supply_by_prod[prod.id]
        dem = demand_by_prod[prod.id]
        results.append(
            {
                "product_code": prod.code,
                "product_name": prod.name,
                "unit": prod.unit,
                "total_supply": sup,
                "total_open_demand": dem,
                "net_balance": sup - dem,
                "shortage_flag": sup < dem,
            }
        )
    return results


@router.get("/overview")
def get_comprehensive_analytics_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Comprehensive dynamically calculated analytics across Supply Chain, Optimization,
    Dispatch Management, and Disaster Scenario Simulations (Phase 6).

    Explicitly separates current live operational database metrics from historical
    optimization run snapshots, persisted dispatch records, and isolated scenario runs.
    """
    warehouses = list(db.scalars(select(Warehouse).order_by(Warehouse.code)).all())
    hospitals = list(db.scalars(select(Hospital).order_by(Hospital.code)).all())
    products = list(db.scalars(select(Product).order_by(Product.code)).all())
    inventories = list(db.scalars(select(Inventory)).all())
    demands = list(db.scalars(select(Demand)).all())

    wh_by_id = {w.id: w for w in warehouses}
    hosp_by_id = {h.id: h for h in hospitals}

    # --- 6.1 Supply Chain KPIs (Current Live Operational Data) ---
    stock_by_wh: dict[int, int] = defaultdict(int)
    total_available_inventory = 0
    for inv in inventories:
        avail = max(0, int(inv.quantity_available))
        stock_by_wh[inv.warehouse_id] += avail
        total_available_inventory += avail

    total_storage_capacity = sum(max(0, int(w.storage_capacity_units)) for w in warehouses)
    inventory_utilization_pct = (
        round((total_available_inventory / total_storage_capacity) * 100.0, 2)
        if total_storage_capacity > 0
        else 0.0
    )

    open_demand = 0
    partially_fulfilled_demand = 0
    fulfilled_demand = 0
    pending_approval_demand = 0
    critical_priority_demand = 0

    for dem in demands:
        qty = int(dem.quantity_requested)
        is_approved = dem.approval_status in (None, "approved")
        if dem.status == "pending_approval":
            pending_approval_demand += qty
        elif dem.status == "open" and is_approved:
            open_demand += qty
        elif dem.status == "partially_fulfilled" and is_approved:
            partially_fulfilled_demand += qty
        elif dem.status == "fulfilled":
            fulfilled_demand += qty

        if dem.status in {"open", "partially_fulfilled"} and is_approved:
            hosp = hosp_by_id.get(dem.hospital_id)
            if dem.priority_level == "critical" or (hosp and hosp.priority_level == "critical"):
                critical_priority_demand += qty

    actionable_demand = open_demand + partially_fulfilled_demand

    warehouse_inventory_utilization = [
        {
            "warehouse_code": w.code,
            "warehouse_name": w.name,
            "area": w.area,
            "stock_units": stock_by_wh[w.id],
            "storage_capacity_units": int(w.storage_capacity_units),
            "utilization_pct": round(
                (stock_by_wh[w.id] / w.storage_capacity_units) * 100.0, 2
            )
            if w.storage_capacity_units > 0
            else 0.0,
        }
        for w in warehouses
    ]

    supply_demand_gap = get_supply_demand_gap(db)

    # --- 6.2 Optimization KPIs (Historical Solver Snapshots) ---
    opt_runs = list(
        db.scalars(
            select(OptimizationRun).order_by(
                OptimizationRun.created_at.desc(), OptimizationRun.id.desc()
            )
        ).all()
    )
    latest_run_payload: dict[str, Any] | None = None
    if opt_runs:
        lr = opt_runs[0]
        rs = lr.summary_json or {}
        run_total_demand = float(
            rs.get("total_demand", lr.total_allocated + lr.total_unmet_demand)
        )
        run_fulfillment = float(
            rs.get(
                "fulfillment_percentage",
                round((lr.total_allocated / run_total_demand) * 100.0, 2)
                if run_total_demand > 0
                else 100.0,
            )
        )
        latest_run_payload = {
            "id": lr.id,
            "run_code": lr.run_code,
            "model_type": lr.model_type,
            "solver_status": lr.solver_status,
            "executed_at": lr.created_at.isoformat() if lr.created_at else None,
            "total_demand": round(run_total_demand, 2),
            "total_allocated": round(lr.total_allocated, 2),
            "total_unmet_demand": round(lr.total_unmet_demand, 2),
            "fulfillment_percentage": round(run_fulfillment, 2),
            "total_cost": round(lr.total_cost, 2),
            "execution_time_ms": round(lr.execution_time_ms, 2),
            "selected_scope": rs.get("selected_scope"),
            "priority_summary": rs.get("priority_summary", []),
            "warehouse_utilization": rs.get("warehouse_utilization", []),
            "hospital_summary": rs.get("hospital_summary", []),
        }

    cost_comparison_history = []
    for run in reversed(opt_runs[:8]):
        rs = run.summary_json or {}
        denom = float(rs.get("total_demand", run.total_allocated + run.total_unmet_demand))
        fulf = round((run.total_allocated / denom) * 100.0, 2) if denom > 0 else 100.0
        cost_comparison_history.append(
            {
                "run_code": run.run_code,
                "short_label": f"#{run.id} ({'Priority' if run.model_type == 'lexicographic_priority' else 'Transport'})",
                "model_type": run.model_type,
                "total_cost": round(run.total_cost, 2),
                "fulfillment_percentage": fulf,
                "total_allocated": round(run.total_allocated, 2),
                "total_unmet_demand": round(run.total_unmet_demand, 2),
            }
        )

    # --- 6.3 Dispatch KPIs (Persisted Dispatch Plans & Shipment Lines) ---
    dispatch_plans = list(
        db.scalars(
            select(DispatchPlan).order_by(DispatchPlan.created_at.desc(), DispatchPlan.id.desc())
        ).all()
    )
    assignments = list(db.scalars(select(VehicleAssignment)).all())
    stops = list(db.scalars(select(DeliveryStop)).all())
    shipment_lines = list(db.scalars(select(ShipmentLine)).all())
    veh_by_id = {v.id: v for v in db.scalars(select(Vehicle)).all()}

    total_planned_qty = round(sum(float(line.quantity_planned) for line in shipment_lines), 2)
    total_delivered_qty = round(sum(float(line.quantity_delivered) for line in shipment_lines), 2)
    total_pending_qty = round(max(0.0, total_planned_qty - total_delivered_qty), 2)
    dispatch_completion_pct = (
        round((total_delivered_qty / total_planned_qty) * 100.0, 2)
        if total_planned_qty > 0
        else 0.0
    )

    avg_vehicle_util = (
        round(sum(float(a.utilization_pct) for a in assignments) / len(assignments), 2)
        if assignments
        else 0.0
    )

    status_counts: dict[str, int] = defaultdict(int)
    for stop in stops:
        status_counts[stop.status] += 1
    dispatch_status_breakdown = [
        {"status": st, "label": st.replace("_", " ").title(), "count": cnt}
        for st, cnt in sorted(status_counts.items())
    ]

    latest_plan = dispatch_plans[0] if dispatch_plans else None
    vehicle_utilization_chart = []
    if latest_plan:
        for va in latest_plan.vehicle_assignments:
            veh = veh_by_id.get(va.vehicle_id)
            wh = wh_by_id.get(va.warehouse_id)
            geom_meta = va.route_geometry_json if isinstance(va.route_geometry_json, dict) else {}
            vehicle_utilization_chart.append(
                {
                    "label": f"{veh.vehicle_code if veh else f'VEH-{va.vehicle_id}'} (W{va.trip_number})",
                    "vehicle_code": veh.vehicle_code if veh else f"VEH-{va.vehicle_id}",
                    "warehouse_code": wh.code if wh else f"WH-{va.warehouse_id}",
                    "trip_number": va.trip_number,
                    "total_load_kg": round(va.total_load_kg, 2),
                    "capacity_kg": round(va.capacity_kg, 2),
                    "utilization_pct": round(va.utilization_pct, 2),
                    "route_distance_km": round(va.route_distance_km, 2),
                    "estimated_duration_min": round(va.estimated_duration_min, 1),
                    "routing_source": geom_meta.get(
                        "routing_source",
                        (latest_plan.summary_json or {}).get("routing_source", "synthetic_fallback"),
                    ),
                }
            )

    # --- 6.4 Scenario Analytics (Isolated Disaster Simulations) ---
    scenario_runs = list(
        db.scalars(
            select(ScenarioRun).order_by(ScenarioRun.created_at.desc(), ScenarioRun.id.desc())
        ).all()
    )
    scen_by_id = {s.id: s for s in db.scalars(select(Scenario)).all()}
    run_code_by_id = {r.id: r.run_code for r in opt_runs}

    impact_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    recent_simulations = []
    for sr in scenario_runs:
        scen = scen_by_id.get(sr.scenario_id)
        stype = scen.scenario_type if scen else (sr.parameters_json or {}).get("scenario_type", "custom")
        comp = sr.comparison_json or {}
        impact_buckets[stype].append(comp)
        if len(recent_simulations) < 6:
            recent_simulations.append(
                {
                    "id": sr.id,
                    "simulation_code": sr.simulation_code,
                    "scenario_name": scen.name if scen else f"Scenario #{sr.scenario_id}",
                    "scenario_type": stype,
                    "baseline_run_code": run_code_by_id.get(sr.baseline_run_id),
                    "status": sr.status,
                    "transport_cost_delta": float(comp.get("transport_cost_delta", 0.0)),
                    "fulfillment_pct_delta": float(comp.get("fulfillment_pct_delta", 0.0)),
                    "route_distance_km_delta": float(comp.get("route_distance_km_delta", 0.0)),
                    "unmet_demand_delta": float(comp.get("unmet_demand_delta", 0.0)),
                }
            )

    impact_by_type = []
    for stype, comps in sorted(impact_buckets.items()):
        count = len(comps)
        impact_by_type.append(
            {
                "scenario_type": stype,
                "label": stype.replace("_", " ").title(),
                "simulations_count": count,
                "avg_cost_delta": round(
                    sum(float(c.get("transport_cost_delta", 0.0)) for c in comps) / count, 2
                ),
                "avg_fulfillment_delta": round(
                    sum(float(c.get("fulfillment_pct_delta", 0.0)) for c in comps) / count, 2
                ),
                "avg_distance_delta": round(
                    sum(float(c.get("route_distance_km_delta", 0.0)) for c in comps) / count, 2
                ),
                "avg_unmet_delta": round(
                    sum(float(c.get("unmet_demand_delta", 0.0)) for c in comps) / count, 2
                ),
            }
        )

    latest_simulation_payload: dict[str, Any] | None = None
    if scenario_runs:
        ls = scenario_runs[0]
        scen = scen_by_id.get(ls.scenario_id)
        map_meta = ls.disrupted_routes_json or {}
        latest_simulation_payload = {
            "id": ls.id,
            "simulation_code": ls.simulation_code,
            "scenario_name": scen.name if scen else f"Scenario #{ls.scenario_id}",
            "scenario_type": scen.scenario_type if scen else "custom",
            "baseline_run_code": run_code_by_id.get(ls.baseline_run_id),
            "status": ls.status,
            "routing_source": map_meta.get("routing_source", "synthetic_fallback"),
            "baseline_metrics": ls.baseline_metrics_json or {},
            "disrupted_metrics": ls.disrupted_metrics_json or {},
            "comparison": ls.comparison_json or {},
        }

    return {
        "supply_chain": {
            "scope_note": "Current live operational database records",
            "total_warehouses": len(warehouses),
            "total_hospitals": len(hospitals),
            "total_products": len(products),
            "available_inventory_units": total_available_inventory,
            "total_storage_capacity_units": total_storage_capacity,
            "inventory_utilization_pct": inventory_utilization_pct,
            "total_actionable_demand_units": actionable_demand,
            "open_demand_units": open_demand,
            "partially_fulfilled_demand_units": partially_fulfilled_demand,
            "fulfilled_demand_units": fulfilled_demand,
            "pending_approval_demand_units": pending_approval_demand,
            "critical_priority_demand_units": critical_priority_demand,
            "warehouse_inventory_utilization": warehouse_inventory_utilization,
            "supply_demand_gap": supply_demand_gap,
        },
        "optimization": {
            "scope_note": "Historical immutable optimization solver snapshot",
            "total_runs": len(opt_runs),
            "latest_run": latest_run_payload,
            "cost_comparison_history": cost_comparison_history,
        },
        "dispatch": {
            "scope_note": "Persisted OR-Tools vehicle routing and delivery tracking",
            "total_dispatch_plans": len(dispatch_plans),
            "total_planned_routes": len(assignments),
            "total_delivery_stops": len(stops),
            "total_dispatched_payload_kg": round(sum(float(a.total_load_kg) for a in assignments), 2),
            "total_estimated_distance_km": round(sum(float(a.route_distance_km) for a in assignments), 2),
            "total_estimated_duration_min": round(
                sum(float(a.estimated_duration_min) for a in assignments), 1
            ),
            "average_vehicle_utilization_pct": avg_vehicle_util,
            "total_planned_quantity": total_planned_qty,
            "total_delivered_quantity": total_delivered_qty,
            "total_pending_quantity": total_pending_qty,
            "dispatch_completion_pct": dispatch_completion_pct,
            "latest_plan_code": latest_plan.plan_code if latest_plan else None,
            "latest_plan_status": latest_plan.status if latest_plan else None,
            "latest_plan_routing_source": (
                (latest_plan.summary_json or {}).get("routing_source", "synthetic_fallback")
                if latest_plan
                else None
            ),
            "status_breakdown": dispatch_status_breakdown,
            "vehicle_utilization_chart": vehicle_utilization_chart,
        },
        "scenarios": {
            "scope_note": "Isolated disaster stress-test simulations (zero live DB mutation)",
            "total_simulations": len(scenario_runs),
            "impact_by_type": impact_by_type,
            "latest_simulation": latest_simulation_payload,
            "recent_simulations": recent_simulations,
        },
    }
