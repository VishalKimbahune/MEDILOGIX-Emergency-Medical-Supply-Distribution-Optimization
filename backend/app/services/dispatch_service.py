"""
Dispatch Management & Vehicle Routing Service (Phase 4A & 4B).

Orchestrates:
- Converting completed Phase 3 LP allocations into per-depot Google OR-Tools CVRP inputs
- Persisting DispatchPlan, VehicleAssignment, DeliveryStop, and ShipmentLine records
- Validating dispatch & stop lifecycle state transitions
- Ensuring zero mutation of live warehouse inventory or hospital demand records
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.dispatch import DeliveryStop, DispatchPlan, ShipmentLine, VehicleAssignment
from app.models.hospital import Hospital
from app.models.optimization_run import OptimizationRun
from app.models.product import Product
from app.models.road import Road
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse
from app.optimization.osm_road_network import OSM_ATTRIBUTION
from app.optimization.vehicle_routing import (
    TRAVEL_TIME_DISCLAIMER,
    DepotRoutingInput,
    MultiDepotRoutingResult,
    RoutingObjective,
    ShipmentLineInput,
    VRPStopInput,
    VRPVehicleInput,
    solve_multi_depot_vrp,
)
from app.schemas.dispatch import (
    DeliveryStopResponse,
    DispatchPlanCreateRequest,
    DispatchPlanDetailResponse,
    DispatchPlanSummaryResponse,
    DispatchStatusUpdateRequest,
    ShipmentLineResponse,
    StopStatusUpdateRequest,
    VehicleAssignmentResponse,
    VehicleResponse,
)
from app.services import audit_service, road_network_service

# Valid dispatch lifecycle transitions
VALID_TRANSITIONS: dict[str, set[str]] = {
    "planned": {"dispatched", "cancelled"},
    "dispatched": {"in_transit", "partially_delivered", "delivered", "cancelled"},
    "in_transit": {"partially_delivered", "delivered", "cancelled"},
    "partially_delivered": {"in_transit", "delivered", "cancelled"},
    "delivered": set(),
    "cancelled": set(),
}


class DispatchDomainError(Exception):
    """Domain validation error with an explicit HTTP status code."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def list_vehicles(db: Session) -> list[VehicleResponse]:
    """List all fleet vehicles with their assigned warehouse metadata."""
    wh_map = {w.id: w for w in db.scalars(select(Warehouse)).all()}
    driver_map = {
        u.id: u.full_name
        for u in db.scalars(select(User).where(User.role == "delivery")).all()
    }
    vehicles = list(db.scalars(select(Vehicle).order_by(Vehicle.vehicle_code)).all())
    return [
        VehicleResponse(
            id=v.id,
            vehicle_code=v.vehicle_code,
            warehouse_id=v.warehouse_id,
            warehouse_code=wh_map[v.warehouse_id].code if v.warehouse_id in wh_map else None,
            warehouse_area=wh_map[v.warehouse_id].area if v.warehouse_id in wh_map else None,
            vehicle_type=v.vehicle_type,
            capacity_kg=v.capacity_kg,
            status=v.status,
            assigned_driver_user_id=v.assigned_driver_user_id,
            assigned_driver_name=driver_map.get(v.assigned_driver_user_id)
            if v.assigned_driver_user_id
            else None,
        )
        for v in vehicles
    ]


def build_depot_inputs_from_allocations(
    allocations: list[dict[str, Any]],
    warehouses_by_id: dict[int, Warehouse],
    hospitals_by_id: dict[int, Hospital],
    products_by_id: dict[int, Product],
    roads: list[Road],
    vehicles: list[Vehicle],
    *,
    allow_multi_trip: bool = True,
    max_trips_per_vehicle: int = 3,
    allow_split_deliveries: bool = True,
    routing_objective: RoutingObjective = "min_distance",
    closed_route_codes: set[str] | None = None,
    closed_way_ids: set[int] | None = None,
    disabled_vehicle_codes: set[str] | None = None,
    search_time_limit_sec: int = 2,
    osm_cache_path: Path | None = None,
    osm_graph_override: nx.MultiDiGraph | nx.DiGraph | None = None,
) -> list[DepotRoutingInput]:
    """
    Convert LP allocation rows into separate DepotRoutingInput objects per warehouse.

    Builds a shared directed OSM road-network matrix (distance, estimated travel time,
    and street geometry) when a valid cached OSM graph is available, with automatic
    graceful fallback to synthetic corridors if OSM data is missing or invalid.

    Allocation rows must have keys: warehouse_id, hospital_id, product_id, quantity_allocated.
    Reused by both DispatchPlan generation and Phase 4C/5 Disaster Scenario Simulation.
    """
    closed_codes = closed_route_codes or set()
    blocked_ways = {int(w) for w in (closed_way_ids or set())}
    disabled_vehs = disabled_vehicle_codes or set()

    road_by_pair: dict[tuple[int, int], Road] = {
        (r.warehouse_id, r.hospital_id): r for r in roads
    }

    vehicles_by_wh: dict[int, list[VRPVehicleInput]] = defaultdict(list)
    for v in vehicles:
        eff_status = "unavailable" if v.vehicle_code in disabled_vehs else v.status
        vehicles_by_wh[v.warehouse_id].append(
            VRPVehicleInput(
                vehicle_id=v.id,
                vehicle_code=v.vehicle_code,
                vehicle_type=v.vehicle_type,
                capacity_kg=v.capacity_kg,
                status=eff_status,
            )
        )

    # Group allocations: warehouse_id -> hospital_id -> product_id -> qty
    grouped: dict[int, dict[int, dict[int, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )
    for alloc in allocations:
        qty = float(alloc["quantity_allocated"])
        if qty <= 1e-6:
            continue
        wh_id = int(alloc["warehouse_id"])
        hosp_id = int(alloc["hospital_id"])
        prod_id = int(alloc["product_id"])
        grouped[wh_id][hosp_id][prod_id] += qty

    # Collect active facilities involved in allocations to compute OSM matrix once
    facilities_payload: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    closed_facility_pairs: set[tuple[str, str]] = set()

    for wh_id in sorted(grouped.keys()):
        wh = warehouses_by_id.get(wh_id)
        if not wh:
            raise DispatchDomainError(f"Invalid warehouse reference id={wh_id} in allocations.", 400)
        if wh.code not in seen_codes:
            facilities_payload.append(
                {"code": wh.code, "type": "warehouse", "lat": wh.latitude, "lon": wh.longitude}
            )
            seen_codes.add(wh.code)

        for hosp_id in sorted(grouped[wh_id].keys()):
            hosp = hospitals_by_id.get(hosp_id)
            if not hosp:
                raise DispatchDomainError(
                    f"Invalid hospital reference id={hosp_id} in allocations.", 400
                )
            if hosp.code not in seen_codes:
                facilities_payload.append(
                    {"code": hosp.code, "type": "hospital", "lat": hosp.latitude, "lon": hosp.longitude}
                )
                seen_codes.add(hosp.code)

            road = road_by_pair.get((wh_id, hosp_id))
            if road and (not road.is_available or road.route_code in closed_codes):
                closed_facility_pairs.add((wh.code, hosp.code))

    routing_source, osm_matrix, fallback_warning = (
        road_network_service.build_facility_routing_matrix(
            facilities_payload,
            routing_objective=routing_objective,
            closed_way_ids=blocked_ways,
            closed_facility_pairs=closed_facility_pairs,
            vehicle_type="medical_truck",
            cache_path=osm_cache_path,
            graph_override=osm_graph_override,
        )
        if facilities_payload
        else ("synthetic_fallback", None, None)
    )

    depot_inputs: list[DepotRoutingInput] = []
    for wh_id in sorted(grouped.keys()):
        wh = warehouses_by_id[wh_id]
        stops: list[VRPStopInput] = []
        for hosp_id in sorted(grouped[wh_id].keys()):
            hosp = hospitals_by_id[hosp_id]

            lines: list[ShipmentLineInput] = []
            for prod_id, qty in sorted(grouped[wh_id][hosp_id].items()):
                prod = products_by_id.get(prod_id)
                if not prod:
                    continue
                lines.append(
                    ShipmentLineInput(
                        product_id=prod.id,
                        product_code=prod.code,
                        product_name=prod.name,
                        unit=prod.unit,
                        quantity=round(qty, 4),
                        unit_weight_kg=float(prod.unit_weight_kg),
                    )
                )

            road = road_by_pair.get((wh_id, hosp_id))
            if routing_source == "osm":
                # In OSM mode, a stop is open unless its named corridor is explicitly closed in DB/request
                corridor_open = True
                if road and (not road.is_available or road.route_code in closed_codes):
                    corridor_open = False
            else:
                corridor_open = bool(road.is_available) if road else False
                if road and road.route_code in closed_codes:
                    corridor_open = False

            stops.append(
                VRPStopInput(
                    hospital_id=hosp.id,
                    hospital_code=hosp.code,
                    hospital_name=hosp.name,
                    area=hosp.area,
                    priority_level=hosp.priority_level,
                    latitude=hosp.latitude,
                    longitude=hosp.longitude,
                    shipment_lines=lines,
                    corridor_distance_km=road.distance_km if road else None,
                    corridor_time_min=road.estimated_travel_time_min if road else None,
                    corridor_available=corridor_open,
                    route_code=road.route_code if road else f"{wh.code}->{hosp.code}",
                )
            )

        depot_inputs.append(
            DepotRoutingInput(
                warehouse_id=wh.id,
                warehouse_code=wh.code,
                warehouse_name=wh.name,
                area=wh.area,
                latitude=wh.latitude,
                longitude=wh.longitude,
                vehicles=vehicles_by_wh.get(wh_id, []),
                stops=stops,
                allow_multi_trip=allow_multi_trip,
                max_trips_per_vehicle=max_trips_per_vehicle,
                allow_split_deliveries=allow_split_deliveries,
                search_time_limit_sec=search_time_limit_sec,
                routing_objective=routing_objective,
                routing_source="osm" if routing_source == "osm" else "synthetic_fallback",
                osm_legs=osm_matrix.legs if osm_matrix is not None else None,
                closed_way_ids=osm_matrix.closed_way_ids if osm_matrix is not None else sorted(blocked_ways),
                closed_osm_ways=osm_matrix.closed_osm_ways if osm_matrix is not None else [],
                fallback_warning=fallback_warning,
                attribution=(
                    osm_matrix.attribution
                    if osm_matrix is not None
                    else "Synthetic Pune Corridor Estimate (OSM fallback)"
                ),
            )
        )

    return depot_inputs


def route_allocations_in_memory(
    db: Session,
    allocations: list[dict[str, Any]],
    *,
    allow_multi_trip: bool = True,
    max_trips_per_vehicle: int = 3,
    allow_split_deliveries: bool = True,
    routing_objective: RoutingObjective = "min_distance",
    closed_route_codes: set[str] | None = None,
    closed_way_ids: set[int] | None = None,
    disabled_vehicle_codes: set[str] | None = None,
    search_time_limit_sec: int = 2,
    osm_cache_path: Path | None = None,
    osm_graph_override: nx.MultiDiGraph | nx.DiGraph | None = None,
) -> MultiDepotRoutingResult:
    """Solve multi-depot OR-Tools CVRP without persisting to dispatch tables (used by scenarios)."""
    warehouses = {w.id: w for w in db.scalars(select(Warehouse)).all()}
    hospitals = {h.id: h for h in db.scalars(select(Hospital)).all()}
    products = {p.id: p for p in db.scalars(select(Product)).all()}
    roads = list(db.scalars(select(Road)).all())
    vehicles = list(db.scalars(select(Vehicle)).all())

    depots = build_depot_inputs_from_allocations(
        allocations=allocations,
        warehouses_by_id=warehouses,
        hospitals_by_id=hospitals,
        products_by_id=products,
        roads=roads,
        vehicles=vehicles,
        allow_multi_trip=allow_multi_trip,
        max_trips_per_vehicle=max_trips_per_vehicle,
        allow_split_deliveries=allow_split_deliveries,
        routing_objective=routing_objective,
        closed_route_codes=closed_route_codes,
        closed_way_ids=closed_way_ids,
        disabled_vehicle_codes=disabled_vehicle_codes,
        search_time_limit_sec=search_time_limit_sec,
        osm_cache_path=osm_cache_path,
        osm_graph_override=osm_graph_override,
    )
    return solve_multi_depot_vrp(depots)


def generate_dispatch_plan(
    db: Session,
    request: DispatchPlanCreateRequest,
    *,
    osm_cache_path: Path | None = None,
    osm_graph_override: nx.MultiDiGraph | nx.DiGraph | None = None,
) -> DispatchPlanDetailResponse:
    """
    Generate and persist a multi-depot OR-Tools DispatchPlan from an OptimizationRun.

    - Uses cached OSM directed road geometry when available; gracefully falls back to
      synthetic corridors when OSM cache is missing or invalid.
    - Never modifies live warehouse inventory or hospital demands.
    - Always initializes plan, assignments, and stops to status='planned' with
      quantity_delivered=0.0.
    - Raises DispatchDomainError (404/400/422) on missing runs, invalid codes,
      or completely infeasible routing.
    """
    opt_run = db.get(OptimizationRun, request.optimization_run_id)
    if not opt_run:
        raise DispatchDomainError(
            f"Optimization run id={request.optimization_run_id} not found.", 404
        )
    if opt_run.solver_status != "Optimal":
        raise DispatchDomainError(
            f"Cannot generate routes from optimization run '{opt_run.run_code}' because its "
            f"solver status is '{opt_run.solver_status}'.",
            400,
        )

    alloc_rows = list(
        db.scalars(
            select(Allocation).where(Allocation.optimization_run_id == opt_run.id)
        ).all()
    )
    if not alloc_rows:
        raise DispatchDomainError(
            f"Optimization run '{opt_run.run_code}' contains zero planned allocations.", 400
        )

    # Validate closed route codes & disabled vehicle codes if supplied
    roads = list(db.scalars(select(Road)).all())
    vehicles = list(db.scalars(select(Vehicle)).all())
    known_routes = {r.route_code for r in roads}
    unknown_routes = sorted(set(request.closed_route_codes) - known_routes)
    if unknown_routes:
        raise DispatchDomainError(
            f"Unknown road corridor code(s): {', '.join(unknown_routes)}.", 400
        )

    known_vehicles = {v.vehicle_code for v in vehicles}
    unknown_vehicles = sorted(set(request.disabled_vehicle_codes) - known_vehicles)
    if unknown_vehicles:
        raise DispatchDomainError(
            f"Unknown vehicle code(s): {', '.join(unknown_vehicles)}.", 400
        )

    alloc_dicts = [
        {
            "warehouse_id": a.warehouse_id,
            "hospital_id": a.hospital_id,
            "product_id": a.product_id,
            "quantity_allocated": a.quantity_allocated,
        }
        for a in alloc_rows
    ]

    warehouses = {w.id: w for w in db.scalars(select(Warehouse)).all()}
    hospitals = {h.id: h for h in db.scalars(select(Hospital)).all()}
    products = {p.id: p for p in db.scalars(select(Product)).all()}

    depots = build_depot_inputs_from_allocations(
        allocations=alloc_dicts,
        warehouses_by_id=warehouses,
        hospitals_by_id=hospitals,
        products_by_id=products,
        roads=roads,
        vehicles=vehicles,
        allow_multi_trip=request.allow_multi_trip,
        max_trips_per_vehicle=request.max_trips_per_vehicle,
        allow_split_deliveries=request.allow_split_deliveries,
        routing_objective=request.routing_objective,
        closed_route_codes=set(request.closed_route_codes),
        closed_way_ids=set(request.closed_way_ids),
        disabled_vehicle_codes=set(request.disabled_vehicle_codes),
        search_time_limit_sec=request.search_time_limit_sec,
        osm_cache_path=osm_cache_path,
        osm_graph_override=osm_graph_override,
    )

    vrp_result = solve_multi_depot_vrp(depots)

    if vrp_result.status == "Infeasible" and not vrp_result.routes:
        reason_text = " ".join(vrp_result.infeasibility_reasons) or "No feasible vehicle route exists."
        raise DispatchDomainError(f"Vehicle routing infeasible: {reason_text}", 422)

    plan_code = f"DSP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"
    depot_summaries = [
        {
            "warehouse_id": d.warehouse_id,
            "warehouse_code": d.warehouse_code,
            "warehouse_name": d.warehouse_name,
            "status": d.status,
            "routing_source": d.routing_source,
            "routing_objective": d.routing_objective,
            "vehicles_available": d.vehicles_available,
            "vehicles_used": d.vehicles_used,
            "routes_count": len(d.routes),
            "total_distance_km": d.total_distance_km,
            "total_duration_min": d.total_duration_min,
            "total_weight_kg": d.total_weight_kg,
            "unreachable_hospitals": d.unreachable_hospitals,
            "infeasibility_reasons": d.infeasibility_reasons,
        }
        for d in vrp_result.depot_results
    ]

    plan = DispatchPlan(
        plan_code=plan_code,
        optimization_run_id=opt_run.id,
        status="planned",
        solver_status=vrp_result.status,
        total_vehicles_used=vrp_result.total_vehicles_used,
        total_routes=vrp_result.total_routes,
        total_stops=vrp_result.total_stops,
        total_distance_km=vrp_result.total_distance_km,
        estimated_duration_min=vrp_result.estimated_duration_min,
        total_weight_kg=vrp_result.total_weight_kg,
        allow_multi_trip=request.allow_multi_trip,
        allow_split_deliveries=request.allow_split_deliveries,
        notes=request.notes or vrp_result.notes,
        summary_json={
            "routing_source": vrp_result.routing_source,
            "routing_objective": vrp_result.routing_objective,
            "infeasibility_reasons": vrp_result.infeasibility_reasons,
            "unreachable_hospitals": vrp_result.unreachable_hospitals,
            "unreachable_connections": vrp_result.unreachable_connections,
            "depot_summaries": depot_summaries,
            "closed_route_codes": list(request.closed_route_codes),
            "closed_way_ids": vrp_result.closed_way_ids,
            "closed_osm_ways": vrp_result.closed_osm_ways,
            "disabled_vehicle_codes": list(request.disabled_vehicle_codes),
            "fallback_warning": vrp_result.fallback_warning,
            "attribution": vrp_result.attribution,
            "travel_time_disclaimer": vrp_result.travel_time_disclaimer,
            "execution_time_ms": vrp_result.execution_time_ms,
        },
    )
    db.add(plan)
    db.flush()

    veh_by_id = {v.id: v for v in vehicles}
    notified_wh_ids: set[int] = set()
    notified_driver_ids: set[int] = set()
    notified_hosp_ids: set[int] = set()

    for route in vrp_result.routes:
        veh_obj = veh_by_id.get(route.vehicle_id)
        driver_uid = veh_obj.assigned_driver_user_id if veh_obj else None
        va = VehicleAssignment(
            dispatch_plan_id=plan.id,
            vehicle_id=route.vehicle_id,
            warehouse_id=route.warehouse_id,
            assigned_driver_user_id=driver_uid,
            trip_number=route.trip_number,
            status="planned",
            preparation_status="pending",
            total_load_kg=route.total_load_kg,
            capacity_kg=route.capacity_kg,
            utilization_pct=route.utilization_pct,
            route_distance_km=route.route_distance_km,
            estimated_duration_min=route.estimated_duration_min,
            route_coordinates_json=route.route_coordinates,
            route_geometry_json={
                "routing_source": route.routing_source,
                "routing_objective": route.routing_objective,
                "geometry": route.route_geometry,
                "way_ids": route.osm_way_ids,
                "road_names": route.road_names,
                "legs": route.leg_details,
                "attribution": vrp_result.attribution,
            },
        )
        db.add(va)
        db.flush()
        notified_wh_ids.add(route.warehouse_id)
        if driver_uid:
            notified_driver_ids.add(driver_uid)

        for stop in route.stops:
            notified_hosp_ids.add(stop.hospital_id)
            ds = DeliveryStop(
                vehicle_assignment_id=va.id,
                hospital_id=stop.hospital_id,
                stop_sequence=stop.stop_sequence,
                status="planned",
                leg_distance_km=stop.leg_distance_km,
                cumulative_distance_km=stop.cumulative_distance_km,
                estimated_arrival_min=stop.estimated_arrival_min,
                stop_weight_kg=stop.stop_weight_kg,
            )
            db.add(ds)
            db.flush()

            for line in stop.shipment_lines:
                db.add(
                    ShipmentLine(
                        delivery_stop_id=ds.id,
                        product_id=int(line["product_id"]),
                        quantity_planned=float(line["quantity_planned"]),
                        quantity_delivered=0.0,  # Never auto-marked delivered
                        unit_weight_kg=float(line["unit_weight_kg"]),
                        total_weight_kg=float(line["total_weight_kg"]),
                    )
                )

    # Notify affected warehouse staff, delivery drivers, and hospitals
    for wh_id in notified_wh_ids:
        audit_service.notify_users_by_role(
            db,
            role="warehouse",
            warehouse_id=wh_id,
            title="New Outgoing Dispatch Plan",
            message=f"Dispatch plan {plan_code} requires shipment preparation at your warehouse.",
            category="dispatch",
            entity_type="dispatch_plan",
            entity_id=plan.id,
        )
    for driver_uid in notified_driver_ids:
        audit_service.create_notification(
            db,
            user_id=driver_uid,
            title="New Delivery Route Assigned",
            message=f"You have been assigned a delivery route under dispatch plan {plan_code}.",
            category="delivery",
            entity_type="dispatch_plan",
            entity_id=plan.id,
        )
    for hosp_id in notified_hosp_ids:
        audit_service.notify_users_by_role(
            db,
            role="hospital",
            hospital_id=hosp_id,
            title="Shipment Scheduled for Your Hospital",
            message=f"Dispatch plan {plan_code} includes scheduled deliveries to your hospital.",
            category="dispatch",
            entity_type="dispatch_plan",
            entity_id=plan.id,
        )

    db.commit()
    db.refresh(plan)
    return get_dispatch_plan_detail(db, plan.id)


def list_dispatch_plans(db: Session) -> list[DispatchPlanSummaryResponse]:
    """List persisted dispatch plans ordered most recent first."""
    plans = list(
        db.scalars(
            select(DispatchPlan).order_by(DispatchPlan.created_at.desc(), DispatchPlan.id.desc())
        ).all()
    )
    run_map = {r.id: r.run_code for r in db.scalars(select(OptimizationRun)).all()}
    return [
        DispatchPlanSummaryResponse(
            id=p.id,
            plan_code=p.plan_code,
            optimization_run_id=p.optimization_run_id,
            optimization_run_code=run_map.get(p.optimization_run_id),
            status=p.status,
            solver_status=p.solver_status,
            routing_source=(p.summary_json or {}).get("routing_source", "synthetic_fallback"),
            routing_objective=(p.summary_json or {}).get("routing_objective", "min_distance"),
            total_vehicles_used=p.total_vehicles_used,
            total_routes=p.total_routes,
            total_stops=p.total_stops,
            total_distance_km=p.total_distance_km,
            estimated_duration_min=p.estimated_duration_min,
            total_weight_kg=p.total_weight_kg,
            allow_multi_trip=p.allow_multi_trip,
            allow_split_deliveries=p.allow_split_deliveries,
            created_at=p.created_at,
        )
        for p in plans
    ]


def get_dispatch_plan_detail(db: Session, plan_id: int) -> DispatchPlanDetailResponse:
    """Return full dispatch plan hierarchy with enriched codes, road geometry, and shipment lines."""
    plan = db.get(DispatchPlan, plan_id)
    if not plan:
        raise DispatchDomainError(f"Dispatch plan id={plan_id} not found.", 404)

    opt_run = db.get(OptimizationRun, plan.optimization_run_id)
    wh_map = {w.id: w for w in db.scalars(select(Warehouse)).all()}
    hosp_map = {h.id: h for h in db.scalars(select(Hospital)).all()}
    prod_map = {p.id: p for p in db.scalars(select(Product)).all()}
    veh_map = {v.id: v for v in db.scalars(select(Vehicle)).all()}
    driver_map = {
        u.id: u.full_name
        for u in db.scalars(select(User).where(User.role == "delivery")).all()
    }
    summary = plan.summary_json or {}
    plan_source = summary.get("routing_source", "synthetic_fallback")
    plan_objective = summary.get("routing_objective", "min_distance")

    assignments_out: list[VehicleAssignmentResponse] = []
    for va in plan.vehicle_assignments:
        veh = veh_map.get(va.vehicle_id)
        wh = wh_map.get(va.warehouse_id)
        stops_out: list[DeliveryStopResponse] = []

        for stop in va.delivery_stops:
            hosp = hosp_map.get(stop.hospital_id)
            lines_out = [
                ShipmentLineResponse(
                    id=line.id,
                    product_id=line.product_id,
                    product_code=prod_map[line.product_id].code
                    if line.product_id in prod_map
                    else f"PROD-{line.product_id}",
                    product_name=prod_map[line.product_id].name
                    if line.product_id in prod_map
                    else f"Product #{line.product_id}",
                    unit=prod_map[line.product_id].unit if line.product_id in prod_map else "units",
                    quantity_planned=line.quantity_planned,
                    quantity_delivered=line.quantity_delivered,
                    unit_weight_kg=line.unit_weight_kg,
                    total_weight_kg=line.total_weight_kg,
                )
                for line in stop.shipment_lines
            ]
            stops_out.append(
                DeliveryStopResponse(
                    id=stop.id,
                    hospital_id=stop.hospital_id,
                    hospital_code=hosp.code if hosp else f"HOSP-{stop.hospital_id}",
                    hospital_name=hosp.name if hosp else f"Hospital #{stop.hospital_id}",
                    hospital_area=hosp.area if hosp else "",
                    priority_level=hosp.priority_level if hosp else "normal",
                    latitude=hosp.latitude if hosp else 0.0,
                    longitude=hosp.longitude if hosp else 0.0,
                    stop_sequence=stop.stop_sequence,
                    status=stop.status,
                    leg_distance_km=stop.leg_distance_km,
                    cumulative_distance_km=stop.cumulative_distance_km,
                    estimated_arrival_min=stop.estimated_arrival_min,
                    stop_weight_kg=stop.stop_weight_kg,
                    notes=stop.notes,
                    shipment_lines=lines_out,
                )
            )

        geom_meta = va.route_geometry_json if isinstance(va.route_geometry_json, dict) else None
        raw_coords = va.route_coordinates_json or []
        if geom_meta and geom_meta.get("geometry"):
            va_geometry = geom_meta["geometry"]
            va_source = geom_meta.get("routing_source", plan_source)
            va_objective = geom_meta.get("routing_objective", plan_objective)
            va_way_ids = geom_meta.get("way_ids", [])
            va_road_names = geom_meta.get("road_names", [])
        else:
            # Backward-compatible synthesis for historical Phase 4 rows without route_geometry_json
            va_geometry = [
                [pt["lat"], pt["lon"]]
                for pt in raw_coords
                if isinstance(pt, dict) and "lat" in pt and "lon" in pt
            ]
            va_source = plan_source
            va_objective = plan_objective
            va_way_ids = []
            va_road_names = []

        assignments_out.append(
            VehicleAssignmentResponse(
                id=va.id,
                vehicle_id=va.vehicle_id,
                vehicle_code=veh.vehicle_code if veh else f"VEH-{va.vehicle_id}",
                vehicle_type=veh.vehicle_type if veh else "medical_van",
                warehouse_id=va.warehouse_id,
                warehouse_code=wh.code if wh else f"WH-{va.warehouse_id}",
                warehouse_name=wh.name if wh else f"Warehouse #{va.warehouse_id}",
                trip_number=va.trip_number,
                status=va.status,
                assigned_driver_user_id=va.assigned_driver_user_id,
                assigned_driver_name=driver_map.get(va.assigned_driver_user_id)
                if va.assigned_driver_user_id
                else None,
                preparation_status=va.preparation_status,
                total_load_kg=va.total_load_kg,
                capacity_kg=va.capacity_kg,
                utilization_pct=va.utilization_pct,
                route_distance_km=va.route_distance_km,
                estimated_duration_min=va.estimated_duration_min,
                routing_source=va_source,
                routing_objective=va_objective,
                fallback_used=(va_source != "osm"),
                geometry_point_count=len(va_geometry),
                stop_count=len(stops_out),
                route_coordinates=raw_coords,
                route_geometry=va_geometry,
                osm_way_ids=va_way_ids,
                road_names=va_road_names,
                delivery_stops=stops_out,
            )
        )

    return DispatchPlanDetailResponse(
        id=plan.id,
        plan_code=plan.plan_code,
        optimization_run_id=plan.optimization_run_id,
        optimization_run_code=opt_run.run_code if opt_run else None,
        status=plan.status,
        solver_status=plan.solver_status,
        routing_source=plan_source,
        routing_objective=plan_objective,
        total_vehicles_used=plan.total_vehicles_used,
        total_routes=plan.total_routes,
        total_stops=plan.total_stops,
        total_distance_km=plan.total_distance_km,
        estimated_duration_min=plan.estimated_duration_min,
        total_weight_kg=plan.total_weight_kg,
        allow_multi_trip=plan.allow_multi_trip,
        allow_split_deliveries=plan.allow_split_deliveries,
        created_at=plan.created_at,
        notes=plan.notes,
        infeasibility_reasons=summary.get("infeasibility_reasons", []),
        depot_summaries=summary.get("depot_summaries", []),
        closed_route_codes=summary.get("closed_route_codes", []),
        closed_way_ids=summary.get("closed_way_ids", []),
        closed_osm_ways=summary.get("closed_osm_ways", []),
        unreachable_hospitals=summary.get("unreachable_hospitals", []),
        unreachable_connections=summary.get("unreachable_connections", []),
        fallback_used=(plan_source != "osm"),
        fallback_warning=summary.get("fallback_warning"),
        attribution=summary.get("attribution", OSM_ATTRIBUTION),
        travel_time_disclaimer=summary.get("travel_time_disclaimer", TRAVEL_TIME_DISCLAIMER),
        vehicle_assignments=assignments_out,
    )


def _validate_transition(current_status: str, new_status: str, entity_label: str) -> None:
    if current_status == new_status:
        return
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        allowed_desc = ", ".join(sorted(allowed)) if allowed else "none (terminal state)"
        raise DispatchDomainError(
            f"Invalid {entity_label} status transition from '{current_status}' to '{new_status}'. "
            f"Allowed next statuses: {allowed_desc}.",
            422,
        )


def update_dispatch_plan_status(
    db: Session, plan_id: int, payload: DispatchStatusUpdateRequest
) -> DispatchPlanDetailResponse:
    """Validate and apply a dispatch lifecycle transition to a DispatchPlan and its child routes."""
    plan = db.get(DispatchPlan, plan_id)
    if not plan:
        raise DispatchDomainError(f"Dispatch plan id={plan_id} not found.", 404)

    _validate_transition(plan.status, payload.status, "dispatch plan")
    plan.status = payload.status
    if payload.notes is not None:
        plan.notes = payload.notes

    # Cascade non-terminal lifecycle progression down to active assignments & stops
    for va in plan.vehicle_assignments:
        if va.status in {"delivered", "cancelled"}:
            continue
        if payload.status in {"dispatched", "in_transit", "cancelled", "delivered"}:
            va.status = payload.status
        for stop in va.delivery_stops:
            if stop.status in {"delivered", "cancelled"}:
                continue
            if payload.status in {"dispatched", "in_transit", "cancelled", "delivered"}:
                stop.status = payload.status
            if payload.status == "delivered":
                for line in stop.shipment_lines:
                    line.quantity_delivered = line.quantity_planned

    db.commit()
    return get_dispatch_plan_detail(db, plan.id)


def _rollup_parent_statuses(plan: DispatchPlan) -> None:
    """Recompute VehicleAssignment and DispatchPlan statuses from individual DeliveryStops."""
    for va in plan.vehicle_assignments:
        stop_statuses = [s.status for s in va.delivery_stops]
        if not stop_statuses:
            continue
        if all(st == "delivered" for st in stop_statuses):
            va.status = "delivered"
        elif all(st == "cancelled" for st in stop_statuses):
            va.status = "cancelled"
        elif any(st in {"delivered", "partially_delivered"} for st in stop_statuses):
            va.status = "partially_delivered"
        elif any(st == "in_transit" for st in stop_statuses):
            va.status = "in_transit"
        elif any(st == "dispatched" for st in stop_statuses):
            va.status = "dispatched"

    va_statuses = [va.status for va in plan.vehicle_assignments]
    if not va_statuses:
        return
    if all(st == "delivered" for st in va_statuses):
        plan.status = "delivered"
    elif all(st == "cancelled" for st in va_statuses):
        plan.status = "cancelled"
    elif any(st in {"delivered", "partially_delivered"} for st in va_statuses):
        plan.status = "partially_delivered"
    elif any(st == "in_transit" for st in va_statuses):
        plan.status = "in_transit"
    elif any(st == "dispatched" for st in va_statuses):
        plan.status = "dispatched"


def update_delivery_stop_status(
    db: Session, stop_id: int, payload: StopStatusUpdateRequest
) -> DispatchPlanDetailResponse:
    """Update delivery completion status at an individual hospital stop and roll up plan status."""
    stop = db.get(DeliveryStop, stop_id)
    if not stop:
        raise DispatchDomainError(f"Delivery stop id={stop_id} not found.", 404)

    _validate_transition(stop.status, payload.status, "delivery stop")
    stop.status = payload.status
    if payload.notes is not None:
        stop.notes = payload.notes

    line_by_id = {line.id: line for line in stop.shipment_lines}
    if payload.shipment_updates:
        for upd in payload.shipment_updates:
            line = line_by_id.get(upd.shipment_line_id)
            if not line:
                raise DispatchDomainError(
                    f"Shipment line id={upd.shipment_line_id} does not belong to stop id={stop_id}.",
                    400,
                )
            if upd.quantity_delivered > line.quantity_planned + 1e-4:
                raise DispatchDomainError(
                    f"Delivered quantity ({upd.quantity_delivered}) cannot exceed planned "
                    f"quantity ({line.quantity_planned}) for shipment line id={line.id}.",
                    422,
                )
            line.quantity_delivered = round(upd.quantity_delivered, 4)
    elif payload.status == "delivered":
        for line in stop.shipment_lines:
            line.quantity_delivered = line.quantity_planned

    va = stop.vehicle_assignment
    plan = va.dispatch_plan
    _rollup_parent_statuses(plan)

    db.commit()
    return get_dispatch_plan_detail(db, plan.id)
