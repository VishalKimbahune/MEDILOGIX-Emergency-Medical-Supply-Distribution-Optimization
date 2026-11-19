"""
Disaster & Disruption Scenario Simulation Service (Phase 4C).

Workflow:
1. Validate baseline OptimizationRun and all disruption entity codes.
2. Snapshot live operational data in memory without modifying any live table.
3. Apply isolated disruptions (warehouse outage, road closure, hospital demand spike,
   vehicle unavailability, or combined).
4. Recalculate supply allocations via Phase 3 OR engine (LP / Lexicographic Priority).
5. Recalculate multi-depot vehicle routes via Phase 4A Google OR-Tools CVRP for
   both baseline and disrupted states.
6. Compute side-by-side comparison KPIs and persist an immutable ScenarioRun record.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.demand import Demand
from app.models.hospital import Hospital
from app.models.inventory import Inventory
from app.models.optimization_run import OptimizationRun
from app.models.product import Product
from app.models.road import Road
from app.models.scenario import Scenario
from app.models.scenario_run import ScenarioRun
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse
from app.optimization.linear_programming import NetworkOptimizationInput
from app.optimization.priority import solve_lexicographic_priority_optimization
from app.optimization.transportation import solve_transportation_problem
from app.optimization.vehicle_routing import MultiDepotRoutingResult
from app.schemas.scenario import (
    ScenarioMetricsSnapshot,
    ScenarioRunDetailResponse,
    ScenarioRunSummaryResponse,
    ScenarioSimulationRequest,
)
from app.services.dispatch_service import route_allocations_in_memory
from app.simulation.scenario_engine import DisasterScenarioConfig, apply_disaster_scenario


class ScenarioDomainError(Exception):
    """Domain validation error for disaster scenario simulation."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _extract_tier_fulfillment(priority_summary: list[dict[str, Any]], tier: str) -> float:
    for item in priority_summary:
        if item.get("priority_level") == tier:
            return float(item.get("fulfillment_pct", 100.0))
    return 100.0


def _serialize_routes_for_map(vrp_res: MultiDepotRoutingResult) -> list[dict[str, Any]]:
    return [
        {
            "warehouse_code": r.warehouse_code,
            "warehouse_name": r.warehouse_name,
            "vehicle_code": r.vehicle_code,
            "vehicle_type": r.vehicle_type,
            "trip_number": r.trip_number,
            "total_load_kg": r.total_load_kg,
            "capacity_kg": r.capacity_kg,
            "utilization_pct": r.utilization_pct,
            "route_distance_km": r.route_distance_km,
            "estimated_duration_min": r.estimated_duration_min,
            "routing_source": r.routing_source,
            "routing_objective": r.routing_objective,
            "route_coordinates": r.route_coordinates,
            "route_geometry": r.route_geometry,
            "osm_way_ids": r.osm_way_ids,
            "road_names": r.road_names,
            "stops": [
                {
                    "hospital_code": s.hospital_code,
                    "hospital_name": s.hospital_name,
                    "priority_level": s.priority_level,
                    "stop_sequence": s.stop_sequence,
                    "stop_weight_kg": s.stop_weight_kg,
                    "estimated_arrival_min": s.estimated_arrival_min,
                }
                for s in r.stops
            ],
        }
        for r in vrp_res.routes
    ]


def _build_baseline_network_snapshot(
    db: Session,
    selected_scope: dict[str, list[str]] | None = None,
) -> tuple[
    NetworkOptimizationInput,
    dict[str, Warehouse],
    dict[str, Hospital],
    dict[str, Product],
    dict[str, Road],
    list[Vehicle],
]:
    """Read-only snapshot of live operational tables scoped to match the baseline run."""
    warehouses = list(db.scalars(select(Warehouse).where(Warehouse.status == "active")).all())
    hospitals = list(db.scalars(select(Hospital).where(Hospital.status == "active")).all())
    products = list(db.scalars(select(Product)).all())

    if selected_scope:
        if selected_scope.get("warehouses"):
            wh_scope = set(selected_scope["warehouses"])
            warehouses = [w for w in warehouses if w.code in wh_scope]
        if selected_scope.get("hospitals"):
            hosp_scope = set(selected_scope["hospitals"])
            hospitals = [h for h in hospitals if h.code in hosp_scope]
        if selected_scope.get("products"):
            prod_scope = set(selected_scope["products"])
            products = [p for p in products if p.code in prod_scope]

    inventories = list(db.scalars(select(Inventory)).all())
    demands = list(
        db.scalars(
            select(Demand).where(
                Demand.status.in_(["open", "partially_fulfilled"]),
                or_(Demand.approval_status == "approved", Demand.approval_status.is_(None)),
            )
        ).all()
    )
    roads = list(db.scalars(select(Road)).all())
    scoped_wh_ids = {w.id for w in warehouses}
    vehicles = [
        v for v in db.scalars(select(Vehicle)).all() if v.warehouse_id in scoped_wh_ids
    ]

    wh_by_id = {w.id: w for w in warehouses}
    hosp_by_id = {h.id: h for h in hospitals}
    prod_by_id = {p.id: p for p in products}

    supply: dict[tuple[str, str], float] = {}
    for inv in inventories:
        wh = wh_by_id.get(inv.warehouse_id)
        prod = prod_by_id.get(inv.product_id)
        if wh and prod:
            supply[(wh.code, prod.code)] = float(
                max(0, inv.quantity_available - inv.quantity_reserved)
            )

    demand_map: dict[tuple[str, str], float] = {}
    for dem in demands:
        hosp = hosp_by_id.get(dem.hospital_id)
        prod = prod_by_id.get(dem.product_id)
        if hosp and prod:
            demand_map[(hosp.code, prod.code)] = (
                demand_map.get((hosp.code, prod.code), 0.0) + float(dem.quantity_requested)
            )

    route_availability: dict[tuple[str, str], bool] = {
        (w.code, h.code): False for w in warehouses for h in hospitals
    }
    unit_cost: dict[tuple[str, str, str], float] = {}
    route_metadata: dict[tuple[str, str], dict[str, Any]] = {}
    road_by_code: dict[str, Road] = {}

    for road in roads:
        road_by_code[road.route_code] = road
        wh = wh_by_id.get(road.warehouse_id)
        hosp = hosp_by_id.get(road.hospital_id)
        if not wh or not hosp:
            continue
        route_availability[(wh.code, hosp.code)] = bool(road.is_available)
        route_metadata[(wh.code, hosp.code)] = {
            "route_code": road.route_code,
            "distance_km": road.distance_km,
            "estimated_travel_time_min": road.estimated_travel_time_min,
        }
        for prod in products:
            unit_cost[(wh.code, hosp.code, prod.code)] = round(
                road.base_transport_cost_per_unit
                + road.distance_km * prod.base_transport_cost_per_km,
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
        product_weight_kg={p.code: p.unit_weight_kg for p in products},
        warehouse_names={w.code: w.name for w in warehouses},
        hospital_names={h.code: h.name for h in hospitals},
        product_names={p.code: p.name for p in products},
        product_units={p.code: p.unit for p in products},
        route_metadata=route_metadata,
    )

    return (
        net_input,
        {w.code: w for w in warehouses},
        {h.code: h for h in hospitals},
        {p.code: p for p in products},
        road_by_code,
        vehicles,
    )


def run_disaster_simulation(
    db: Session,
    request: ScenarioSimulationRequest,
    existing_scenario_id: int | None = None,
) -> ScenarioRunDetailResponse:
    """
    Run an isolated disaster simulation comparing a baseline OptimizationRun
    against recalculated LP allocations and OR-Tools vehicle routes under disruptions.
    """
    start_time = time.perf_counter()

    baseline_run = db.get(OptimizationRun, request.baseline_run_id)
    if not baseline_run:
        raise ScenarioDomainError(
            f"Baseline optimization run id={request.baseline_run_id} not found.", 404
        )

    baseline_scope = (baseline_run.summary_json or {}).get("selected_scope")
    (
        baseline_net,
        wh_by_code,
        hosp_by_code,
        prod_by_code,
        road_by_code,
        vehicles,
    ) = _build_baseline_network_snapshot(db, selected_scope=baseline_scope)

    # Validate disruption inputs against known entities
    unknown_wh = sorted(set(request.disabled_warehouse_codes) - set(wh_by_code.keys()))
    if unknown_wh:
        raise ScenarioDomainError(
            f"Unknown or inactive warehouse code(s): {', '.join(unknown_wh)}.", 400
        )
    unknown_hosp = sorted(set(request.demand_spike_hospital_codes) - set(hosp_by_code.keys()))
    if unknown_hosp:
        raise ScenarioDomainError(
            f"Unknown or inactive hospital code(s): {', '.join(unknown_hosp)}.", 400
        )
    unknown_routes = sorted(set(request.closed_route_codes) - set(road_by_code.keys()))
    if unknown_routes:
        raise ScenarioDomainError(
            f"Unknown road corridor code(s): {', '.join(unknown_routes)}.", 400
        )
    known_vehicles = {v.vehicle_code for v in vehicles}
    unknown_vehs = sorted(set(request.disabled_vehicle_codes) - known_vehicles)
    if unknown_vehs:
        raise ScenarioDomainError(
            f"Unknown vehicle code(s): {', '.join(unknown_vehs)}.", 400
        )

    # 1. Compute Baseline metrics & baseline OR-Tools routing from persisted baseline run
    baseline_alloc_rows = list(
        db.scalars(
            select(Allocation).where(Allocation.optimization_run_id == baseline_run.id)
        ).all()
    )
    baseline_alloc_dicts = [
        {
            "warehouse_id": a.warehouse_id,
            "hospital_id": a.hospital_id,
            "product_id": a.product_id,
            "quantity_allocated": a.quantity_allocated,
        }
        for a in baseline_alloc_rows
    ]
    baseline_vrp = route_allocations_in_memory(
        db,
        baseline_alloc_dicts,
        allow_multi_trip=request.allow_multi_trip,
        max_trips_per_vehicle=request.max_trips_per_vehicle,
        allow_split_deliveries=request.allow_split_deliveries,
        routing_objective=request.routing_objective,
    )

    base_summary = baseline_run.summary_json or {}
    base_priority_summary = base_summary.get("priority_summary", [])
    base_total_demand = float(
        base_summary.get(
            "total_demand", baseline_run.total_allocated + baseline_run.total_unmet_demand
        )
    )
    base_fulfillment = float(
        base_summary.get(
            "fulfillment_percentage",
            round((baseline_run.total_allocated / base_total_demand) * 100.0, 2)
            if base_total_demand > 0
            else 100.0,
        )
    )
    all_available_vehicles = sum(
        1 for v in vehicles if str(v.status).lower() == "available"
    )

    baseline_metrics = ScenarioMetricsSnapshot(
        solver_status=baseline_run.solver_status,
        routing_status=baseline_vrp.status,
        total_demand=round(base_total_demand, 2),
        total_allocated=round(baseline_run.total_allocated, 2),
        total_unmet_demand=round(baseline_run.total_unmet_demand, 2),
        fulfillment_percentage=base_fulfillment,
        critical_fulfillment_pct=_extract_tier_fulfillment(base_priority_summary, "critical"),
        high_fulfillment_pct=_extract_tier_fulfillment(base_priority_summary, "high"),
        normal_fulfillment_pct=_extract_tier_fulfillment(base_priority_summary, "normal"),
        total_transport_cost=round(baseline_run.total_cost, 2),
        total_route_distance_km=baseline_vrp.total_distance_km,
        estimated_route_duration_min=baseline_vrp.estimated_duration_min,
        available_vehicles_count=all_available_vehicles,
        completed_feasible_routes=baseline_vrp.total_routes,
        infeasibility_reasons=baseline_vrp.infeasibility_reasons,
    )

    # 2. Apply isolated disruptions to in-memory network snapshot
    wh_id_to_code = {w.id: w.code for w in wh_by_code.values()}
    hosp_id_to_code = {h.id: h.code for h in hosp_by_code.values()}
    closed_pairs: set[tuple[str, str]] = set()
    closed_corridors_map: list[dict[str, Any]] = []

    for r_code in request.closed_route_codes:
        road = road_by_code[r_code]
        wc = wh_id_to_code.get(road.warehouse_id)
        hc = hosp_id_to_code.get(road.hospital_id)
        if wc and hc:
            closed_pairs.add((wc, hc))
            wh_obj = wh_by_code[wc]
            h_obj = hosp_by_code[hc]
            closed_corridors_map.append(
                {
                    "route_code": r_code,
                    "warehouse_code": wc,
                    "hospital_code": hc,
                    "distance_km": road.distance_km,
                    "from_lat": wh_obj.latitude,
                    "from_lon": wh_obj.longitude,
                    "to_lat": h_obj.latitude,
                    "to_lon": h_obj.longitude,
                }
            )

    scenario_cfg = DisasterScenarioConfig(
        name=request.name or f"Scenario-{request.scenario_type}",
        disabled_warehouses=set(request.disabled_warehouse_codes),
        closed_routes=closed_pairs,
        demand_spike_hospitals=set(request.demand_spike_hospital_codes),
        demand_spike_pct=request.demand_spike_pct,
        disabled_vehicles=set(request.disabled_vehicle_codes),
    )
    disrupted_net = apply_disaster_scenario(baseline_net, scenario_cfg)

    # Effective available vehicles after warehouse outages & vehicle unavailability
    disabled_wh_ids = {
        wh_by_code[c].id for c in request.disabled_warehouse_codes if c in wh_by_code
    }
    disrupted_available_vehicles = sum(
        1
        for v in vehicles
        if str(v.status).lower() == "available"
        and v.warehouse_id not in disabled_wh_ids
        and v.vehicle_code not in set(request.disabled_vehicle_codes)
    )

    # 3. Recalculate LP allocations & OR-Tools vehicle routing under disruption
    if not disrupted_net.warehouses:
        # Total warehouse collapse edge case: 0 supply, 100% unmet
        disrupted_total_demand = round(sum(disrupted_net.demand.values()), 2)
        disrupted_vrp = MultiDepotRoutingResult(
            status="Infeasible",
            infeasibility_reasons=["All active warehouses were disabled in this scenario."],
        )
        disrupted_metrics = ScenarioMetricsSnapshot(
            solver_status="Infeasible (No Active Warehouses)",
            routing_status="Infeasible",
            total_demand=disrupted_total_demand,
            total_allocated=0.0,
            total_unmet_demand=disrupted_total_demand,
            fulfillment_percentage=0.0,
            critical_fulfillment_pct=0.0,
            high_fulfillment_pct=0.0,
            normal_fulfillment_pct=0.0,
            total_transport_cost=0.0,
            total_route_distance_km=0.0,
            estimated_route_duration_min=0.0,
            available_vehicles_count=0,
            completed_feasible_routes=0,
            infeasibility_reasons=disrupted_vrp.infeasibility_reasons,
        )
        sim_status = "infeasible"
    else:
        if baseline_run.model_type == "transportation_lp":
            disrupted_lp = solve_transportation_problem(disrupted_net, allow_unmet_demand=True)
        else:
            disrupted_lp = solve_lexicographic_priority_optimization(disrupted_net)

        disrupted_alloc_dicts = [
            {
                "warehouse_id": wh_by_code[a["warehouse_code"]].id,
                "hospital_id": hosp_by_code[a["hospital_code"]].id,
                "product_id": prod_by_code[a["product_code"]].id,
                "quantity_allocated": a["quantity_allocated"],
            }
            for a in disrupted_lp.allocations
            if a["warehouse_code"] in wh_by_code
            and a["hospital_code"] in hosp_by_code
            and a["product_code"] in prod_by_code
        ]

        disrupted_vrp = route_allocations_in_memory(
            db,
            disrupted_alloc_dicts,
            allow_multi_trip=request.allow_multi_trip,
            max_trips_per_vehicle=request.max_trips_per_vehicle,
            allow_split_deliveries=request.allow_split_deliveries,
            routing_objective=request.routing_objective,
            closed_route_codes=set(request.closed_route_codes),
            closed_way_ids=set(request.closed_way_ids),
            disabled_vehicle_codes=set(request.disabled_vehicle_codes),
        )

        disrupted_metrics = ScenarioMetricsSnapshot(
            solver_status=disrupted_lp.solver_status,
            routing_status=disrupted_vrp.status,
            total_demand=round(disrupted_lp.total_demand, 2),
            total_allocated=round(disrupted_lp.total_allocated, 2),
            total_unmet_demand=round(disrupted_lp.total_unmet_demand, 2),
            fulfillment_percentage=disrupted_lp.fulfillment_percentage,
            critical_fulfillment_pct=_extract_tier_fulfillment(
                disrupted_lp.priority_summary, "critical"
            ),
            high_fulfillment_pct=_extract_tier_fulfillment(disrupted_lp.priority_summary, "high"),
            normal_fulfillment_pct=_extract_tier_fulfillment(
                disrupted_lp.priority_summary, "normal"
            ),
            total_transport_cost=disrupted_lp.total_cost,
            total_route_distance_km=disrupted_vrp.total_distance_km,
            estimated_route_duration_min=disrupted_vrp.estimated_duration_min,
            available_vehicles_count=disrupted_available_vehicles,
            completed_feasible_routes=disrupted_vrp.total_routes,
            infeasibility_reasons=disrupted_vrp.infeasibility_reasons,
        )
        sim_status = (
            "completed"
            if disrupted_vrp.status in {"Optimal", "Empty"}
            else "partial"
            if disrupted_vrp.status == "Partial"
            else "infeasible"
        )

    # 4. Build Baseline vs. Disrupted Comparison Deltas
    comparison = {
        "demand_delta": round(disrupted_metrics.total_demand - baseline_metrics.total_demand, 2),
        "allocated_delta": round(
            disrupted_metrics.total_allocated - baseline_metrics.total_allocated, 2
        ),
        "unmet_demand_delta": round(
            disrupted_metrics.total_unmet_demand - baseline_metrics.total_unmet_demand, 2
        ),
        "fulfillment_pct_delta": round(
            disrupted_metrics.fulfillment_percentage - baseline_metrics.fulfillment_percentage, 2
        ),
        "critical_fulfillment_delta": round(
            disrupted_metrics.critical_fulfillment_pct
            - baseline_metrics.critical_fulfillment_pct,
            2,
        ),
        "high_fulfillment_delta": round(
            disrupted_metrics.high_fulfillment_pct - baseline_metrics.high_fulfillment_pct, 2
        ),
        "normal_fulfillment_delta": round(
            disrupted_metrics.normal_fulfillment_pct - baseline_metrics.normal_fulfillment_pct, 2
        ),
        "transport_cost_delta": round(
            disrupted_metrics.total_transport_cost - baseline_metrics.total_transport_cost, 2
        ),
        "route_distance_km_delta": round(
            disrupted_metrics.total_route_distance_km - baseline_metrics.total_route_distance_km, 2
        ),
        "route_duration_min_delta": round(
            disrupted_metrics.estimated_route_duration_min
            - baseline_metrics.estimated_route_duration_min,
            1,
        ),
        "available_vehicles_delta": (
            disrupted_metrics.available_vehicles_count - baseline_metrics.available_vehicles_count
        ),
        "completed_routes_delta": (
            disrupted_metrics.completed_feasible_routes - baseline_metrics.completed_feasible_routes
        ),
        "summary_text": (
            f"Under this disruption, total demand changed by {disrupted_metrics.total_demand - baseline_metrics.total_demand:+.0f} units, "
            f"unmet demand shifted by {disrupted_metrics.total_unmet_demand - baseline_metrics.total_unmet_demand:+.0f} units, "
            f"Critical fulfillment moved to {disrupted_metrics.critical_fulfillment_pct:.1f}% "
            f"(High: {disrupted_metrics.high_fulfillment_pct:.1f}%, Normal: {disrupted_metrics.normal_fulfillment_pct:.1f}%), "
            f"and OR-Tools completed {disrupted_metrics.completed_feasible_routes} feasible route(s) "
            f"covering {disrupted_metrics.total_route_distance_km:.2f} km across {disrupted_metrics.available_vehicles_count} available vehicle(s)."
        ),
    }

    # 5. Persist Scenario (if ad-hoc) and immutable ScenarioRun
    params_snapshot = {
        "scenario_type": request.scenario_type,
        "disabled_warehouse_codes": list(request.disabled_warehouse_codes),
        "closed_route_codes": list(request.closed_route_codes),
        "closed_way_ids": [int(w) for w in request.closed_way_ids],
        "demand_spike_hospital_codes": list(request.demand_spike_hospital_codes),
        "demand_spike_pct": request.demand_spike_pct,
        "disabled_vehicle_codes": list(request.disabled_vehicle_codes),
        "routing_objective": request.routing_objective,
        "allow_multi_trip": request.allow_multi_trip,
        "max_trips_per_vehicle": request.max_trips_per_vehicle,
        "allow_split_deliveries": request.allow_split_deliveries,
    }

    if existing_scenario_id is not None:
        scenario = db.get(Scenario, existing_scenario_id)
        if not scenario:
            raise ScenarioDomainError(f"Scenario id={existing_scenario_id} not found.", 404)
    else:
        sim_suffix = uuid4().hex[:5].upper()
        base_name = (request.name or f"{request.scenario_type.replace('_', ' ').title()}").strip()
        existing_same = db.scalar(select(Scenario).where(Scenario.name == base_name))
        scenario_name = f"{base_name} ({sim_suffix})" if existing_same else base_name
        scenario = Scenario(
            name=scenario_name,
            description=request.description
            or f"Disaster simulation comparing against baseline run {baseline_run.run_code}.",
            scenario_type=request.scenario_type,
            parameters_json=params_snapshot,
            is_active=True,
        )
        db.add(scenario)
        db.flush()

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    sim_code = f"SIM-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"

    scenario_run = ScenarioRun(
        simulation_code=sim_code,
        scenario_id=scenario.id,
        baseline_run_id=baseline_run.id,
        status=sim_status,
        parameters_json=params_snapshot,
        baseline_metrics_json=baseline_metrics.model_dump(),
        disrupted_metrics_json=disrupted_metrics.model_dump(),
        comparison_json=comparison,
        disrupted_routes_json={
            "routes": _serialize_routes_for_map(disrupted_vrp),
            "closed_corridors": closed_corridors_map,
            "closed_way_ids": disrupted_vrp.closed_way_ids,
            "closed_osm_ways": disrupted_vrp.closed_osm_ways,
            "disabled_warehouses": list(request.disabled_warehouse_codes),
            "unreachable_hospitals": disrupted_vrp.unreachable_hospitals,
            "routing_source": disrupted_vrp.routing_source,
            "routing_objective": disrupted_vrp.routing_objective,
            "fallback_warning": disrupted_vrp.fallback_warning,
        },
        notes=(
            "Isolated simulation completed without mutating live warehouse inventory, "
            "hospital demand, vehicle fleet, road corridors, or baseline optimization runs."
        ),
        execution_time_ms=elapsed_ms,
    )
    db.add(scenario_run)
    db.commit()
    db.refresh(scenario_run)

    return get_scenario_run_detail(db, scenario_run.id)


def list_scenario_runs(db: Session) -> list[ScenarioRunSummaryResponse]:
    """Return historical disaster scenario simulations ordered most recent first."""
    runs = list(
        db.scalars(
            select(ScenarioRun).order_by(ScenarioRun.created_at.desc(), ScenarioRun.id.desc())
        ).all()
    )
    scen_map = {s.id: s for s in db.scalars(select(Scenario)).all()}
    opt_map = {r.id: r.run_code for r in db.scalars(select(OptimizationRun)).all()}

    return [
        ScenarioRunSummaryResponse(
            id=sr.id,
            simulation_code=sr.simulation_code,
            scenario_id=sr.scenario_id,
            scenario_name=scen_map[sr.scenario_id].name
            if sr.scenario_id in scen_map
            else f"Scenario #{sr.scenario_id}",
            scenario_type=scen_map[sr.scenario_id].scenario_type
            if sr.scenario_id in scen_map
            else "custom",
            baseline_run_id=sr.baseline_run_id,
            baseline_run_code=opt_map.get(sr.baseline_run_id),
            status=sr.status,
            execution_time_ms=sr.execution_time_ms,
            baseline_metrics=ScenarioMetricsSnapshot(**sr.baseline_metrics_json),
            disrupted_metrics=ScenarioMetricsSnapshot(**sr.disrupted_metrics_json),
            created_at=sr.created_at,
        )
        for sr in runs
    ]


def get_scenario_run_detail(db: Session, simulation_id: int) -> ScenarioRunDetailResponse:
    """Return full details of a persisted disaster scenario simulation."""
    sr = db.get(ScenarioRun, simulation_id)
    if not sr:
        raise ScenarioDomainError(f"Scenario simulation id={simulation_id} not found.", 404)

    scenario = db.get(Scenario, sr.scenario_id)
    baseline_run = db.get(OptimizationRun, sr.baseline_run_id)
    map_data = sr.disrupted_routes_json or {}

    return ScenarioRunDetailResponse(
        id=sr.id,
        simulation_code=sr.simulation_code,
        scenario_id=sr.scenario_id,
        scenario_name=scenario.name if scenario else f"Scenario #{sr.scenario_id}",
        scenario_type=scenario.scenario_type if scenario else "custom",
        description=scenario.description if scenario else None,
        baseline_run_id=sr.baseline_run_id,
        baseline_run_code=baseline_run.run_code if baseline_run else None,
        status=sr.status,
        execution_time_ms=sr.execution_time_ms,
        baseline_metrics=ScenarioMetricsSnapshot(**sr.baseline_metrics_json),
        disrupted_metrics=ScenarioMetricsSnapshot(**sr.disrupted_metrics_json),
        created_at=sr.created_at,
        parameters=sr.parameters_json or {},
        comparison=sr.comparison_json or {},
        disrupted_routes=map_data.get("routes", []),
        closed_corridors=map_data.get("closed_corridors", []),
        closed_way_ids=map_data.get("closed_way_ids", []),
        closed_osm_ways=map_data.get("closed_osm_ways", []),
        disabled_warehouses=map_data.get("disabled_warehouses", []),
        unreachable_hospitals=map_data.get("unreachable_hospitals", []),
        routing_source=map_data.get("routing_source", "synthetic_fallback"),
        routing_objective=map_data.get("routing_objective", "min_distance"),
        fallback_warning=map_data.get("fallback_warning"),
        notes=sr.notes,
    )
