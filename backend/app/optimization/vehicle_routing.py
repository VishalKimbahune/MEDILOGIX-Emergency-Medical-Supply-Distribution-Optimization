"""
Multi-Depot Capacitated Vehicle Routing Engine (Google OR-Tools — Phase 4A + Phase 5 Stage 3).

Architecture:
- Strictly decoupled from Phase 3 LP allocation. Phase 3 determines *how much*
  each warehouse sends to each hospital; OR-Tools determines *how vehicles
  transport those exact shipments* without inventing or altering LP quantities.
- Multi-depot strategy: Each warehouse with positive allocations is solved as an
  independent depot-based Capacitated VRP (CVRP), where every vehicle starts and
  finishes at its home warehouse.
- Capacity model: 1D weight-based payload capacity (kg) computed from
  Product.unit_weight_kg.
- Road network integration (Phase 5 Stage 3):
  - When a validated OpenStreetMap (OSM) directed road graph is available,
    all depot-to-hospital, inter-hospital, and return legs use directed OSM
    shortest-path road distances, assumed speed-profile travel times, and real
    street polyline geometry respecting one-way rules, vehicle-access tags, and
    OSM road closures.
  - Supports configurable optimization objective: `min_distance` (default) or
    `min_time` (estimated travel time). Always returns both distance and
    estimated travel time.
  - Unreachable connections in OSM mode are marked unavailable and NEVER
    silently substituted with synthetic estimates.
  - When the OSM road graph is missing or invalid, gracefully falls back to
    the Phase 4 synthetic corridor + urban tortuosity model and labels the
    routing source explicitly (`synthetic_fallback`).
  - Estimated travel times are based on assumed road-class speed profiles and
    do NOT represent live traffic or guaranteed arrival times.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

ROAD_TORTUOSITY_FACTOR: float = 1.28
AVG_URBAN_SPEED_KMPH: float = 28.0
DEFAULT_SEARCH_TIME_LIMIT_SEC: int = 1
WEIGHT_SCALE: int = 10  # 0.1 kg integer precision for OR-Tools
DISTANCE_SCALE: int = 1000  # 1 meter integer precision for OR-Tools
TIME_SCALE: int = 60  # 1 second integer precision for OR-Tools
UNREACHABLE_ARC_COST: int = 10_000_000
TRAVEL_TIME_DISCLAIMER: str = (
    "Estimated travel time based on OpenStreetMap road classification and assumed speeds; "
    "not live traffic or guaranteed arrival times."
)

RoutingObjective = Literal["min_distance", "min_time"]
RoutingSource = Literal["osm", "synthetic_fallback"]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two WGS84 coordinates."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _estimate_inter_hospital_leg(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> tuple[float, float]:
    """Return estimated (distance_km, travel_time_min) between two hospitals."""
    straight = _haversine_km(lat1, lon1, lat2, lon2)
    dist_km = round(max(0.8, straight * ROAD_TORTUOSITY_FACTOR), 2)
    time_min = round(max(3.0, (dist_km / AVG_URBAN_SPEED_KMPH) * 60.0), 1)
    return dist_km, time_min


@dataclass
class ShipmentLineInput:
    """Exact product-level shipment derived from Phase 3 LP Allocation."""

    product_id: int
    product_code: str
    product_name: str
    unit: str
    quantity: float
    unit_weight_kg: float

    @property
    def total_weight_kg(self) -> float:
        return round(self.quantity * self.unit_weight_kg, 4)


@dataclass
class VRPStopInput:
    """Hospital delivery demand node assigned to a specific warehouse depot."""

    hospital_id: int
    hospital_code: str
    hospital_name: str
    area: str
    priority_level: str
    latitude: float
    longitude: float
    shipment_lines: list[ShipmentLineInput]
    corridor_distance_km: float | None = None
    corridor_time_min: float | None = None
    corridor_available: bool = True
    route_code: str | None = None

    @property
    def total_weight_kg(self) -> float:
        return round(sum(line.total_weight_kg for line in self.shipment_lines), 4)


@dataclass
class VRPVehicleInput:
    """Available vehicle stationed at a warehouse depot."""

    vehicle_id: int
    vehicle_code: str
    vehicle_type: str
    capacity_kg: float
    status: str = "available"


@dataclass
class DepotRoutingInput:
    """Complete single-warehouse CVRP problem instance."""

    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    area: str
    latitude: float
    longitude: float
    vehicles: list[VRPVehicleInput]
    stops: list[VRPStopInput]
    allow_multi_trip: bool = True
    max_trips_per_vehicle: int = 3
    allow_split_deliveries: bool = True
    search_time_limit_sec: int = DEFAULT_SEARCH_TIME_LIMIT_SEC
    routing_objective: RoutingObjective = "min_distance"
    routing_source: RoutingSource = "synthetic_fallback"
    osm_legs: dict[tuple[str, str], Any] | None = None
    closed_way_ids: list[int] = field(default_factory=list)
    closed_osm_ways: list[dict[str, Any]] = field(default_factory=list)
    fallback_warning: str | None = None
    attribution: str = "Synthetic Pune Corridor Estimate"


@dataclass
class SolvedStop:
    """Ordered hospital stop inside a solved vehicle tour."""

    hospital_id: int
    hospital_code: str
    hospital_name: str
    area: str
    priority_level: str
    latitude: float
    longitude: float
    stop_sequence: int
    leg_distance_km: float
    cumulative_distance_km: float
    estimated_arrival_min: float
    stop_weight_kg: float
    shipment_lines: list[dict[str, Any]]


@dataclass
class SolvedVehicleRoute:
    """Solved closed-tour vehicle assignment starting and ending at its home warehouse."""

    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    vehicle_id: int
    vehicle_code: str
    vehicle_type: str
    trip_number: int
    capacity_kg: float
    total_load_kg: float
    utilization_pct: float
    route_distance_km: float
    estimated_duration_min: float
    route_coordinates: list[dict[str, Any]]
    stops: list[SolvedStop]
    routing_source: RoutingSource = "synthetic_fallback"
    routing_objective: RoutingObjective = "min_distance"
    route_geometry: list[list[float]] = field(default_factory=list)
    osm_way_ids: list[int] = field(default_factory=list)
    road_names: list[str] = field(default_factory=list)
    leg_details: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DepotRoutingResult:
    """Result of solving CVRP for a single warehouse depot."""

    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    status: str  # Optimal | Partial | Feasible | Infeasible | Empty
    routes: list[SolvedVehicleRoute] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_duration_min: float = 0.0
    total_weight_kg: float = 0.0
    vehicles_available: int = 0
    vehicles_used: int = 0
    infeasibility_reasons: list[str] = field(default_factory=list)
    unreachable_hospitals: list[str] = field(default_factory=list)
    unreachable_connections: list[dict[str, Any]] = field(default_factory=list)
    routing_source: RoutingSource = "synthetic_fallback"
    routing_objective: RoutingObjective = "min_distance"
    fallback_warning: str | None = None
    execution_time_ms: float = 0.0


@dataclass
class MultiDepotRoutingResult:
    """Aggregated result across all warehouse depots."""

    status: str  # Optimal | Partial | Infeasible | Empty
    depot_results: list[DepotRoutingResult] = field(default_factory=list)
    routes: list[SolvedVehicleRoute] = field(default_factory=list)
    total_vehicles_available: int = 0
    total_vehicles_used: int = 0
    total_routes: int = 0
    total_stops: int = 0
    total_distance_km: float = 0.0
    estimated_duration_min: float = 0.0
    total_weight_kg: float = 0.0
    infeasibility_reasons: list[str] = field(default_factory=list)
    unreachable_hospitals: list[str] = field(default_factory=list)
    unreachable_connections: list[dict[str, Any]] = field(default_factory=list)
    routing_source: RoutingSource = "synthetic_fallback"
    routing_objective: RoutingObjective = "min_distance"
    closed_way_ids: list[int] = field(default_factory=list)
    closed_osm_ways: list[dict[str, Any]] = field(default_factory=list)
    fallback_warning: str | None = None
    attribution: str = "Synthetic Pune Corridor Estimate"
    travel_time_disclaimer: str = TRAVEL_TIME_DISCLAIMER
    execution_time_ms: float = 0.0
    notes: str = (
        "Solved with Google OR-Tools CVRP per warehouse depot (1D weight capacity). "
        "Travel times are speed-profile estimates; not live traffic."
    )


def _split_oversized_stop(
    stop: VRPStopInput, max_vehicle_capacity_kg: float
) -> list[VRPStopInput]:
    """
    Split a hospital stop whose total LP weight exceeds the depot's largest vehicle
    into capacity-feasible sub-stops while conserving exact product quantities.
    """
    if stop.total_weight_kg <= max_vehicle_capacity_kg + 1e-6:
        return [stop]

    # Reserve a tiny 0.5% margin for floating-point rounding safety
    chunk_limit_kg = max(1.0, max_vehicle_capacity_kg * 0.995)
    buckets: list[list[ShipmentLineInput]] = []
    current_lines: list[ShipmentLineInput] = []
    current_weight = 0.0

    for line in stop.shipment_lines:
        remaining_qty = float(line.quantity)
        unit_w = max(0.01, float(line.unit_weight_kg))

        while remaining_qty > 1e-6:
            space_kg = chunk_limit_kg - current_weight
            if space_kg < unit_w and current_lines:
                buckets.append(current_lines)
                current_lines = []
                current_weight = 0.0
                space_kg = chunk_limit_kg

            max_units_fit = math.floor(space_kg / unit_w)
            if max_units_fit <= 0:
                # Fractional fallback only if single unit exceeds capacity
                take_qty = min(remaining_qty, round(space_kg / unit_w, 4))
            else:
                take_qty = min(remaining_qty, float(max_units_fit))

            if take_qty <= 1e-6:
                take_qty = remaining_qty

            current_lines.append(
                ShipmentLineInput(
                    product_id=line.product_id,
                    product_code=line.product_code,
                    product_name=line.product_name,
                    unit=line.unit,
                    quantity=round(take_qty, 4),
                    unit_weight_kg=line.unit_weight_kg,
                )
            )
            current_weight += take_qty * unit_w
            remaining_qty = round(remaining_qty - take_qty, 4)

            if current_weight >= chunk_limit_kg - 1e-6 and remaining_qty > 1e-6:
                buckets.append(current_lines)
                current_lines = []
                current_weight = 0.0

    if current_lines:
        buckets.append(current_lines)

    return [
        VRPStopInput(
            hospital_id=stop.hospital_id,
            hospital_code=stop.hospital_code,
            hospital_name=stop.hospital_name,
            area=stop.area,
            priority_level=stop.priority_level,
            latitude=stop.latitude,
            longitude=stop.longitude,
            shipment_lines=bucket,
            corridor_distance_km=stop.corridor_distance_km,
            corridor_time_min=stop.corridor_time_min,
            corridor_available=stop.corridor_available,
            route_code=stop.route_code,
        )
        for bucket in buckets
    ]


def _append_geometry_segment(
    accumulated: list[list[float]], segment: list[list[float]]
) -> None:
    """Append a polyline segment without duplicating adjacent identical vertices."""
    for pt in segment:
        if not accumulated or accumulated[-1] != pt:
            accumulated.append(pt)


def solve_depot_vrp(depot: DepotRoutingInput) -> DepotRoutingResult:
    """
    Solve a single warehouse depot's Capacitated Vehicle Routing Problem via Google OR-Tools.

    Every vehicle starts and finishes at the warehouse depot (index 0).
    Supports both directed OpenStreetMap road-network matrices (`osm`) and
    Phase 4 corridor/Haversine fallback (`synthetic_fallback`), optimizing either
    `min_distance` (default) or `min_time` (estimated travel time).
    """
    start_time = time.perf_counter()
    use_osm = depot.routing_source == "osm" and depot.osm_legs is not None
    eff_source: RoutingSource = "osm" if use_osm else "synthetic_fallback"
    objective: RoutingObjective = (
        "min_time" if depot.routing_objective == "min_time" else "min_distance"
    )

    active_stops = [s for s in depot.stops if s.total_weight_kg > 1e-6]
    available_vehicles = [
        v for v in depot.vehicles if str(v.status).lower() == "available" and v.capacity_kg > 0
    ]

    if not active_stops:
        return DepotRoutingResult(
            warehouse_id=depot.warehouse_id,
            warehouse_code=depot.warehouse_code,
            warehouse_name=depot.warehouse_name,
            status="Empty",
            vehicles_available=len(available_vehicles),
            routing_source=eff_source,
            routing_objective=objective,
            fallback_warning=depot.fallback_warning,
            execution_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
        )

    reasons: list[str] = []
    unreachable_hospitals: list[str] = []
    unreachable_connections: list[dict[str, Any]] = []
    routable_stops: list[VRPStopInput] = []

    # 1. Check corridor closures & OSM road-network reachability (never substitute synthetic legs in OSM mode)
    for stop in active_stops:
        if not stop.corridor_available:
            route_label = stop.route_code or f"{depot.warehouse_code}->{stop.hospital_code}"
            reason = (
                f"Corridor {route_label} between {depot.warehouse_code} and {stop.hospital_code} "
                f"is closed or unavailable."
            )
            reasons.append(reason)
            if stop.hospital_code not in unreachable_hospitals:
                unreachable_hospitals.append(stop.hospital_code)
            unreachable_connections.append(
                {
                    "from_code": depot.warehouse_code,
                    "to_code": stop.hospital_code,
                    "reason": reason,
                }
            )
            continue

        if use_osm and depot.osm_legs is not None:
            outbound = depot.osm_legs.get((depot.warehouse_code, stop.hospital_code))
            inbound = depot.osm_legs.get((stop.hospital_code, depot.warehouse_code))
            if outbound is None or not outbound.reachable:
                reason = (
                    getattr(outbound, "reason", None)
                    or f"No open OSM road route from {depot.warehouse_code} to {stop.hospital_code}."
                )
                reasons.append(reason)
                if stop.hospital_code not in unreachable_hospitals:
                    unreachable_hospitals.append(stop.hospital_code)
                unreachable_connections.append(
                    {
                        "from_code": depot.warehouse_code,
                        "to_code": stop.hospital_code,
                        "reason": reason,
                    }
                )
                continue
            if inbound is None or not inbound.reachable:
                reason = (
                    getattr(inbound, "reason", None)
                    or f"No open OSM return road route from {stop.hospital_code} back to {depot.warehouse_code}."
                )
                reasons.append(reason)
                if stop.hospital_code not in unreachable_hospitals:
                    unreachable_hospitals.append(stop.hospital_code)
                unreachable_connections.append(
                    {
                        "from_code": stop.hospital_code,
                        "to_code": depot.warehouse_code,
                        "reason": reason,
                    }
                )
                continue

        routable_stops.append(stop)

    if not routable_stops:
        return DepotRoutingResult(
            warehouse_id=depot.warehouse_id,
            warehouse_code=depot.warehouse_code,
            warehouse_name=depot.warehouse_name,
            status="Infeasible",
            vehicles_available=len(available_vehicles),
            total_weight_kg=round(sum(s.total_weight_kg for s in active_stops), 2),
            infeasibility_reasons=reasons,
            unreachable_hospitals=unreachable_hospitals,
            unreachable_connections=unreachable_connections,
            routing_source=eff_source,
            routing_objective=objective,
            fallback_warning=depot.fallback_warning,
            execution_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
        )

    # 2. Check vehicle availability
    if not available_vehicles:
        reasons.append(
            f"No available vehicles at warehouse {depot.warehouse_code} to transport "
            f"{sum(s.total_weight_kg for s in routable_stops):.1f} kg of allocated supplies."
        )
        return DepotRoutingResult(
            warehouse_id=depot.warehouse_id,
            warehouse_code=depot.warehouse_code,
            warehouse_name=depot.warehouse_name,
            status="Infeasible",
            vehicles_available=0,
            total_weight_kg=round(sum(s.total_weight_kg for s in routable_stops), 2),
            infeasibility_reasons=reasons,
            unreachable_hospitals=unreachable_hospitals,
            unreachable_connections=unreachable_connections,
            routing_source=eff_source,
            routing_objective=objective,
            fallback_warning=depot.fallback_warning,
            execution_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
        )

    # Deterministic vehicle ordering (largest capacity first for clean packing)
    available_vehicles.sort(key=lambda v: (-v.capacity_kg, v.vehicle_code))
    max_vehicle_cap = max(v.capacity_kg for v in available_vehicles)
    total_required_weight = round(sum(s.total_weight_kg for s in routable_stops), 2)

    # 3. Handle oversized individual hospital stops
    expanded_stops: list[VRPStopInput] = []
    capacity_errors: list[str] = []
    for stop in routable_stops:
        if stop.total_weight_kg > max_vehicle_cap + 1e-6:
            if not depot.allow_split_deliveries:
                capacity_errors.append(
                    f"Hospital {stop.hospital_code} shipment ({stop.total_weight_kg:.1f} kg) "
                    f"exceeds maximum vehicle capacity ({max_vehicle_cap:.1f} kg) at "
                    f"{depot.warehouse_code} and split deliveries are disabled."
                )
            else:
                expanded_stops.extend(_split_oversized_stop(stop, max_vehicle_cap))
        else:
            expanded_stops.append(stop)

    if capacity_errors:
        reasons.extend(capacity_errors)
        return DepotRoutingResult(
            warehouse_id=depot.warehouse_id,
            warehouse_code=depot.warehouse_code,
            warehouse_name=depot.warehouse_name,
            status="Infeasible",
            vehicles_available=len(available_vehicles),
            total_weight_kg=total_required_weight,
            infeasibility_reasons=reasons,
            unreachable_hospitals=unreachable_hospitals,
            unreachable_connections=unreachable_connections,
            routing_source=eff_source,
            routing_objective=objective,
            fallback_warning=depot.fallback_warning,
            execution_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
        )

    # 4. Build vehicle trip slots (single-trip or multi-wave)
    max_trips = max(1, depot.max_trips_per_vehicle) if depot.allow_multi_trip else 1
    single_wave_cap = sum(v.capacity_kg for v in available_vehicles)
    total_fleet_cap = single_wave_cap * max_trips

    if total_required_weight > total_fleet_cap + 1e-6:
        mode_desc = (
            f"{max_trips} wave(s)" if depot.allow_multi_trip else "single-trip mode"
        )
        reasons.append(
            f"Insufficient fleet capacity at {depot.warehouse_code}: required "
            f"{total_required_weight:.1f} kg exceeds available capacity ({total_fleet_cap:.1f} kg "
            f"across {len(available_vehicles)} vehicle(s) in {mode_desc})."
        )
        return DepotRoutingResult(
            warehouse_id=depot.warehouse_id,
            warehouse_code=depot.warehouse_code,
            warehouse_name=depot.warehouse_name,
            status="Infeasible",
            vehicles_available=len(available_vehicles),
            total_weight_kg=total_required_weight,
            infeasibility_reasons=reasons,
            unreachable_hospitals=unreachable_hospitals,
            unreachable_connections=unreachable_connections,
            routing_source=eff_source,
            routing_objective=objective,
            fallback_warning=depot.fallback_warning,
            execution_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
        )

    vehicle_slots: list[tuple[VRPVehicleInput, int]] = []
    for trip_num in range(1, max_trips + 1):
        for veh in available_vehicles:
            vehicle_slots.append((veh, trip_num))

    # 5. Construct distance & travel-time matrices (index 0 = depot, 1..N = expanded_stops)
    n_nodes = 1 + len(expanded_stops)
    node_codes = [depot.warehouse_code] + [s.hospital_code for s in expanded_stops]
    dist_km_matrix: list[list[float]] = [[0.0] * n_nodes for _ in range(n_nodes)]
    time_min_matrix: list[list[float]] = [[0.0] * n_nodes for _ in range(n_nodes)]
    reachable_matrix: list[list[bool]] = [[True] * n_nodes for _ in range(n_nodes)]
    leg_obj_matrix: list[list[Any]] = [[None] * n_nodes for _ in range(n_nodes)]

    if use_osm and depot.osm_legs is not None:
        for r in range(n_nodes):
            for c in range(n_nodes):
                if r == c or node_codes[r] == node_codes[c]:
                    dist_km_matrix[r][c] = 0.0
                    time_min_matrix[r][c] = 0.0
                    reachable_matrix[r][c] = True
                    continue
                leg = depot.osm_legs.get((node_codes[r], node_codes[c]))
                if leg is not None and leg.reachable:
                    dist_km_matrix[r][c] = float(leg.distance_km)
                    time_min_matrix[r][c] = float(leg.estimated_travel_time_min)
                    reachable_matrix[r][c] = True
                    leg_obj_matrix[r][c] = leg
                else:
                    dist_km_matrix[r][c] = float(UNREACHABLE_ARC_COST)
                    time_min_matrix[r][c] = float(UNREACHABLE_ARC_COST)
                    reachable_matrix[r][c] = False
                    if r > 0 and c > 0:
                        unreachable_connections.append(
                            {
                                "from_code": node_codes[r],
                                "to_code": node_codes[c],
                                "reason": getattr(leg, "reason", None)
                                or f"No open directed OSM road path from {node_codes[r]} to {node_codes[c]}.",
                            }
                        )
    else:
        for i, stop in enumerate(expanded_stops, start=1):
            if stop.corridor_distance_km is not None and stop.corridor_time_min is not None:
                d_km = float(stop.corridor_distance_km)
                t_min = float(stop.corridor_time_min)
            else:
                d_km, t_min = _estimate_inter_hospital_leg(
                    depot.latitude, depot.longitude, stop.latitude, stop.longitude
                )
            dist_km_matrix[0][i] = d_km
            dist_km_matrix[i][0] = d_km
            time_min_matrix[0][i] = t_min
            time_min_matrix[i][0] = t_min

        for i, stop_a in enumerate(expanded_stops, start=1):
            for j, stop_b in enumerate(expanded_stops, start=1):
                if i == j:
                    continue
                if stop_a.hospital_id == stop_b.hospital_id:
                    dist_km_matrix[i][j] = 0.0
                    time_min_matrix[i][j] = 0.0
                else:
                    d_km, t_min = _estimate_inter_hospital_leg(
                        stop_a.latitude, stop_a.longitude, stop_b.latitude, stop_b.longitude
                    )
                    dist_km_matrix[i][j] = d_km
                    time_min_matrix[i][j] = t_min

    # Integer-scaled objective cost matrix & demands for OR-Tools
    if objective == "min_time":
        cost_int_matrix = [
            [
                UNREACHABLE_ARC_COST
                if not reachable_matrix[r][c]
                else int(round(time_min_matrix[r][c] * TIME_SCALE))
                for c in range(n_nodes)
            ]
            for r in range(n_nodes)
        ]
        fixed_vehicle_cost = 120  # 2-minute equivalent fixed dispatch cost
    else:
        cost_int_matrix = [
            [
                UNREACHABLE_ARC_COST
                if not reachable_matrix[r][c]
                else int(round(dist_km_matrix[r][c] * DISTANCE_SCALE))
                for c in range(n_nodes)
            ]
            for r in range(n_nodes)
        ]
        fixed_vehicle_cost = 500  # 0.5-km equivalent fixed dispatch cost

    demands_int = [0] + [int(math.ceil(stop.total_weight_kg * WEIGHT_SCALE)) for stop in expanded_stops]
    capacities_int = [int(math.floor(veh.capacity_kg * WEIGHT_SCALE)) for veh, _ in vehicle_slots]

    # 6. Configure Google OR-Tools RoutingModel
    manager = pywrapcp.RoutingIndexManager(n_nodes, len(vehicle_slots), 0)
    routing = pywrapcp.RoutingModel(manager)

    def cost_callback(from_index: int, to_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return cost_int_matrix[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(cost_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Explicitly forbid unreachable directed arcs between stops in OR-Tools
    for r in range(1, n_nodes):
        from_idx = manager.NodeToIndex(r)
        for c in range(1, n_nodes):
            if r != c and not reachable_matrix[r][c]:
                to_idx = manager.NodeToIndex(c)
                routing.NextVar(from_idx).RemoveValue(to_idx)

    # Small fixed dispatch cost encourages combining feasible multi-stop tours
    routing.SetFixedCostOfAllVehicles(fixed_vehicle_cost)

    def demand_callback(from_index: int) -> int:
        from_node = manager.IndexToNode(from_index)
        return demands_int[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,  # zero capacity slack
        capacities_int,
        True,  # start cumul to zero
        "Capacity",
    )

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = max(1, int(depot.search_time_limit_sec))
    search_parameters.solution_limit = 50

    solution = routing.SolveWithParameters(search_parameters)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    if solution is None:
        reasons.append(
            f"OR-Tools CVRP solver could not find a feasible vehicle routing plan for warehouse "
            f"{depot.warehouse_code} within {depot.search_time_limit_sec}s (required "
            f"{total_required_weight:.1f} kg across {len(expanded_stops)} stop(s))."
        )
        return DepotRoutingResult(
            warehouse_id=depot.warehouse_id,
            warehouse_code=depot.warehouse_code,
            warehouse_name=depot.warehouse_name,
            status="Infeasible",
            vehicles_available=len(available_vehicles),
            total_weight_kg=total_required_weight,
            infeasibility_reasons=reasons,
            unreachable_hospitals=unreachable_hospitals,
            unreachable_connections=unreachable_connections,
            routing_source=eff_source,
            routing_objective=objective,
            fallback_warning=depot.fallback_warning,
            execution_time_ms=elapsed_ms,
        )

    # 7. Extract solved closed-tour vehicle routes with full geometry & way IDs
    solved_routes: list[SolvedVehicleRoute] = []
    used_vehicle_ids: set[int] = set()
    total_depot_dist = 0.0
    total_depot_time = 0.0

    for slot_idx, (veh, trip_num) in enumerate(vehicle_slots):
        index = routing.Start(slot_idx)
        visited_nodes: list[int] = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                visited_nodes.append(node)
            index = solution.Value(routing.NextVar(index))

        if not visited_nodes:
            continue

        used_vehicle_ids.add(veh.vehicle_id)
        route_stops: list[SolvedStop] = []
        route_coords: list[dict[str, Any]] = [
            {
                "node_type": "warehouse",
                "code": depot.warehouse_code,
                "name": depot.warehouse_name,
                "lat": depot.latitude,
                "lon": depot.longitude,
                "sequence": 0,
            }
        ]
        route_geometry: list[list[float]] = []
        route_way_ids: list[int] = []
        route_road_names: list[str] = []
        leg_details: list[dict[str, Any]] = []

        prev_node = 0
        cum_dist = 0.0
        cum_time = 0.0
        route_load = 0.0

        def _record_leg(src_idx: int, dst_idx: int) -> tuple[float, float]:
            assert reachable_matrix[src_idx][dst_idx], (
                f"OR-Tools selected unreachable arc {node_codes[src_idx]} -> {node_codes[dst_idx]}"
            )
            ld = dist_km_matrix[src_idx][dst_idx]
            lt = time_min_matrix[src_idx][dst_idx]
            leg_obj = leg_obj_matrix[src_idx][dst_idx]
            if use_osm and leg_obj is not None:
                _append_geometry_segment(route_geometry, leg_obj.geometry)
                for wid in leg_obj.way_ids:
                    if not route_way_ids or route_way_ids[-1] != wid:
                        route_way_ids.append(int(wid))
                for rname in leg_obj.road_names:
                    if not route_road_names or route_road_names[-1] != rname:
                        route_road_names.append(str(rname))
                leg_details.append(
                    {
                        "from_code": node_codes[src_idx],
                        "to_code": node_codes[dst_idx],
                        "distance_km": round(ld, 3),
                        "estimated_travel_time_min": round(lt, 1),
                        "way_ids": list(leg_obj.way_ids),
                        "road_names": list(leg_obj.road_names),
                        "point_count": len(leg_obj.geometry),
                    }
                )
            else:
                src_lat = depot.latitude if src_idx == 0 else expanded_stops[src_idx - 1].latitude
                src_lon = depot.longitude if src_idx == 0 else expanded_stops[src_idx - 1].longitude
                dst_lat = depot.latitude if dst_idx == 0 else expanded_stops[dst_idx - 1].latitude
                dst_lon = depot.longitude if dst_idx == 0 else expanded_stops[dst_idx - 1].longitude
                _append_geometry_segment(
                    route_geometry,
                    [[round(src_lat, 6), round(src_lon, 6)], [round(dst_lat, 6), round(dst_lon, 6)]],
                )
                leg_details.append(
                    {
                        "from_code": node_codes[src_idx],
                        "to_code": node_codes[dst_idx],
                        "distance_km": round(ld, 2),
                        "estimated_travel_time_min": round(lt, 1),
                        "way_ids": [],
                        "road_names": [],
                        "point_count": 2,
                    }
                )
            return ld, lt

        for seq_num, node_idx in enumerate(visited_nodes, start=1):
            stop_obj = expanded_stops[node_idx - 1]
            leg_d, leg_t = _record_leg(prev_node, node_idx)
            cum_dist += leg_d
            cum_time += leg_t
            stop_w = stop_obj.total_weight_kg
            route_load += stop_w

            route_stops.append(
                SolvedStop(
                    hospital_id=stop_obj.hospital_id,
                    hospital_code=stop_obj.hospital_code,
                    hospital_name=stop_obj.hospital_name,
                    area=stop_obj.area,
                    priority_level=stop_obj.priority_level,
                    latitude=stop_obj.latitude,
                    longitude=stop_obj.longitude,
                    stop_sequence=seq_num,
                    leg_distance_km=round(leg_d, 2),
                    cumulative_distance_km=round(cum_dist, 2),
                    estimated_arrival_min=round(cum_time, 1),
                    stop_weight_kg=round(stop_w, 2),
                    shipment_lines=[
                        {
                            "product_id": line.product_id,
                            "product_code": line.product_code,
                            "product_name": line.product_name,
                            "unit": line.unit,
                            "quantity_planned": round(line.quantity, 4),
                            "unit_weight_kg": line.unit_weight_kg,
                            "total_weight_kg": round(line.total_weight_kg, 2),
                        }
                        for line in stop_obj.shipment_lines
                    ],
                )
            )
            route_coords.append(
                {
                    "node_type": "hospital",
                    "code": stop_obj.hospital_code,
                    "name": stop_obj.hospital_name,
                    "priority_level": stop_obj.priority_level,
                    "lat": stop_obj.latitude,
                    "lon": stop_obj.longitude,
                    "sequence": seq_num,
                }
            )
            prev_node = node_idx

        # Return leg back to home warehouse depot
        return_dist, return_time = _record_leg(prev_node, 0)
        cum_dist += return_dist
        cum_time += return_time

        route_coords.append(
            {
                "node_type": "warehouse_return",
                "code": depot.warehouse_code,
                "name": f"{depot.warehouse_name} (Return)",
                "lat": depot.latitude,
                "lon": depot.longitude,
                "sequence": len(visited_nodes) + 1,
            }
        )

        # Post-solve safety check: vehicle capacity must never be exceeded
        assert route_load <= veh.capacity_kg + 0.1, (
            f"Capacity invariant violated for {veh.vehicle_code}: {route_load} > {veh.capacity_kg}"
        )

        total_depot_dist += cum_dist
        total_depot_time += cum_time

        solved_routes.append(
            SolvedVehicleRoute(
                warehouse_id=depot.warehouse_id,
                warehouse_code=depot.warehouse_code,
                warehouse_name=depot.warehouse_name,
                vehicle_id=veh.vehicle_id,
                vehicle_code=veh.vehicle_code,
                vehicle_type=veh.vehicle_type,
                trip_number=trip_num,
                capacity_kg=veh.capacity_kg,
                total_load_kg=round(route_load, 2),
                utilization_pct=round((route_load / veh.capacity_kg) * 100.0, 2)
                if veh.capacity_kg > 0
                else 0.0,
                route_distance_km=round(cum_dist, 2),
                estimated_duration_min=round(cum_time, 1),
                route_coordinates=route_coords,
                stops=route_stops,
                routing_source=eff_source,
                routing_objective=objective,
                route_geometry=route_geometry,
                osm_way_ids=route_way_ids,
                road_names=route_road_names,
                leg_details=leg_details,
            )
        )

    # Normalize trip numbers sequentially (1, 2, ...) per vehicle so a single-trip
    # vehicle is always Wave #1 regardless of which OR-Tools slot was selected.
    trip_counters: dict[int, int] = {}
    for route in solved_routes:
        next_trip = trip_counters.get(route.vehicle_id, 0) + 1
        trip_counters[route.vehicle_id] = next_trip
        route.trip_number = next_trip

    depot_status = "Partial" if unreachable_hospitals else "Optimal"

    return DepotRoutingResult(
        warehouse_id=depot.warehouse_id,
        warehouse_code=depot.warehouse_code,
        warehouse_name=depot.warehouse_name,
        status=depot_status,
        routes=solved_routes,
        total_distance_km=round(total_depot_dist, 2),
        total_duration_min=round(total_depot_time, 1),
        total_weight_kg=round(sum(r.total_load_kg for r in solved_routes), 2),
        vehicles_available=len(available_vehicles),
        vehicles_used=len(used_vehicle_ids),
        infeasibility_reasons=reasons,
        unreachable_hospitals=unreachable_hospitals,
        unreachable_connections=unreachable_connections,
        routing_source=eff_source,
        routing_objective=objective,
        fallback_warning=depot.fallback_warning,
        execution_time_ms=elapsed_ms,
    )


def solve_multi_depot_vrp(depots: list[DepotRoutingInput]) -> MultiDepotRoutingResult:
    """
    Solve separate depot-based CVRPs for every warehouse with allocated shipments
    and aggregate all routes, distances, durations, and infeasibility diagnostics.
    """
    start_time = time.perf_counter()
    depot_results: list[DepotRoutingResult] = []
    all_routes: list[SolvedVehicleRoute] = []
    all_reasons: list[str] = []
    all_unreachable_hospitals: list[str] = []
    all_unreachable_connections: list[dict[str, Any]] = []

    for depot in depots:
        res = solve_depot_vrp(depot)
        depot_results.append(res)
        all_routes.extend(res.routes)
        all_reasons.extend(res.infeasibility_reasons)
        for hcode in res.unreachable_hospitals:
            if hcode not in all_unreachable_hospitals:
                all_unreachable_hospitals.append(hcode)
        all_unreachable_connections.extend(res.unreachable_connections)

    non_empty = [d for d in depot_results if d.status != "Empty"]
    if not non_empty:
        overall_status = "Empty"
    elif all(d.status == "Optimal" for d in non_empty):
        overall_status = "Optimal"
    elif any(d.status in {"Optimal", "Partial"} for d in non_empty):
        overall_status = "Partial"
    else:
        overall_status = "Infeasible"

    routing_source: RoutingSource = (
        "osm" if any(d.routing_source == "osm" for d in depots) else "synthetic_fallback"
    )
    routing_objective: RoutingObjective = (
        depots[0].routing_objective if depots else "min_distance"
    )
    fallback_warning = next((d.fallback_warning for d in depots if d.fallback_warning), None)
    closed_way_ids = sorted({wid for d in depots for wid in d.closed_way_ids})
    closed_osm_ways = next((d.closed_osm_ways for d in depots if d.closed_osm_ways), [])
    attribution = (
        depots[0].attribution
        if depots
        else "Synthetic Pune Corridor Estimate"
    )

    source_note = (
        "Solved with Google OR-Tools CVRP on cached OpenStreetMap directed road geometry. "
        if routing_source == "osm"
        else "Solved with Google OR-Tools CVRP using synthetic corridor fallback. "
    )
    objective_note = (
        "Objective: Minimum Estimated Travel Time. "
        if routing_objective == "min_time"
        else "Objective: Minimum Road Distance. "
    )

    total_vehicles_available = sum(d.vehicles_available for d in depot_results)
    unique_vehicles_used = len({r.vehicle_id for r in all_routes})
    total_stops = sum(len(r.stops) for r in all_routes)
    total_dist = round(sum(r.route_distance_km for r in all_routes), 2)
    total_dur = round(sum(r.estimated_duration_min for r in all_routes), 1)
    total_weight = round(sum(r.total_load_kg for r in all_routes), 2)

    return MultiDepotRoutingResult(
        status=overall_status,
        depot_results=depot_results,
        routes=all_routes,
        total_vehicles_available=total_vehicles_available,
        total_vehicles_used=unique_vehicles_used,
        total_routes=len(all_routes),
        total_stops=total_stops,
        total_distance_km=total_dist,
        estimated_duration_min=total_dur,
        total_weight_kg=total_weight,
        infeasibility_reasons=all_reasons,
        unreachable_hospitals=all_unreachable_hospitals,
        unreachable_connections=all_unreachable_connections,
        routing_source=routing_source,
        routing_objective=routing_objective,
        closed_way_ids=closed_way_ids,
        closed_osm_ways=closed_osm_ways,
        fallback_warning=fallback_warning,
        attribution=attribution,
        travel_time_disclaimer=TRAVEL_TIME_DISCLAIMER,
        execution_time_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
        notes=source_note + objective_note + TRAVEL_TIME_DISCLAIMER,
    )
