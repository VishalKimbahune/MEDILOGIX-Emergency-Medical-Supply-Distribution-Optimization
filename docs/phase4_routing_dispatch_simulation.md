# MEDILOGIX — Phase 4 Technical Documentation: Vehicle Routing, Dispatch Management & Disaster Simulation

---

## 1. Distinction Between LP Allocation (Phase 3) and Vehicle Routing (Phase 4)

MEDILOGIX strictly decouples **supply allocation** from **physical vehicle routing**:

| Stage | Module | Solver | Question Answered |
| :--- | :--- | :--- | :--- |
| **Phase 3 (Allocation)** | `transportation.py`, `priority.py` | PuLP CBC (LP) | *How many units* of product $k$ should warehouse $i$ allocate to hospital $j$ to prioritize critical care and minimize transport cost? |
| **Phase 4A (Routing)** | `vehicle_routing.py` | Google OR-Tools (CVRP) | *Which vehicles* at warehouse $i$ transport those exact LP-allocated quantities, and in *what ordered hospital stop sequence*? |

Phase 4A never invents, modifies, or drops LP-allocated quantities; total planned product units across all stops strictly equal the source `OptimizationRun` allocations.

---

## 2. Vehicle Routing Mathematical Formulation (Multi-Depot CVRP)

For each warehouse depot $i \in I$ with positive LP allocations to hospital subset $H_i \subseteq J$:

- **Nodes**: $V_i = \{0\} \cup S_i$, where node $0$ is home warehouse $i$ and $S_i$ is the set of hospital delivery stops (including capacity-feasible split stops when a hospital's shipment weight exceeds the depot's largest truck).
- **Fleet**: Available vehicles $M_i = \{v \in \text{Vehicles}(i) \mid \text{status}(v) = \text{available}\}$, each with payload capacity $Q_v > 0$ (kg). Under multi-wave dispatch (`allow_multi_trip=True`), each vehicle may run up to $W_{\max}$ sequential closed depot tours.
- **Stop Weights**: For stop $s \in S_i$ delivering product lines $L_s$,
  $$q_s = \sum_{(k, q_{s,k}) \in L_s} w_k \, q_{s,k}$$
  where $w_k$ is `Product.unit_weight_kg`.
- **Arc Distances**: $d_{a,b} \ge 0$ is taken from the `roads` corridor table for warehouse-to-hospital legs $(0, s)$ and $(s, 0)$, and estimated via Haversine $\times 1.28$ tortuosity factor for inter-hospital legs $(s_a, s_b)$.
- **Objective**: Minimize total route distance (plus a small fixed dispatch cost per active vehicle slot to prefer efficient multi-stop tours):
  $$\min \sum_{v \in M_i} \sum_{(a,b)} d_{a,b} \, y_{a,b,v} + \sum_{v \in M_i} F \cdot z_v$$
- **Constraints**:
  1. Each stop $s \in S_i$ is visited exactly once by an available depot vehicle.
  2. Every active tour begins and ends at home depot $0$ (no mixing of distinct warehouse origins).
  3. **Capacity**: For every vehicle tour $v$, $\sum_{s \in \text{tour}(v)} q_s \le Q_v$.
  4. **Corridor Availability**: Closed or unavailable warehouse-hospital corridors (`is_available = False` or in `closed_route_codes`) are forbidden and produce explicit infeasibility diagnostics if required.

---

## 3. Google OR-Tools Implementation

Implemented in `backend/app/optimization/vehicle_routing.py` (`ortools>=9.10.0`):

- Uses `pywrapcp.RoutingIndexManager(n_nodes, n_vehicle_slots, depot=0)` and `pywrapcp.RoutingModel`.
- Distances are scaled to integer meters (`DISTANCE_SCALE = 1000`); payload weights and vehicle capacities are scaled to 0.1 kg integer precision (`WEIGHT_SCALE = 10`).
- Capacity is enforced strictly with `routing.AddDimensionWithVehicleCapacity(..., slack_max=0, fix_start_cumul_to_zero=True, name="Capacity")`.
- Deterministic search strategy:
  - `FirstSolutionStrategy.PATH_CHEAPEST_ARC`
  - `LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH`
  - Configurable `time_limit` (default 1s per depot) and `solution_limit = 50`.
- Post-solve assertion verifies `route_load <= vehicle.capacity_kg` on every generated tour.

---

## 4. Capacity Constraints & Multi-Depot Strategy

- **1D Weight-Based Capacity**: All products (`Oxygen Cylinders: 18.5 kg`, `IV Fluid Cartons: 12.0 kg`, `Trauma Kits: 6.5 kg`, `Essential Medicine Boxes: 5.0 kg`) use `Product.unit_weight_kg`. **Cubic volume constraints are not yet modeled.**
- **Split Deliveries & Multi-Wave Trips**:
  - Configurable via `allow_split_deliveries` and `allow_multi_trip` (`max_trips_per_vehicle`).
  - When enabled, oversized hospital shipments are split cleanly across vehicle loads while conserving exact unit counts, and vehicles may run sequential waves from their home depot.
  - When disabled (strict single-trip mode), capacity overflows return explicit `422` infeasibility diagnostics.
- **Separate Depot Routing**: Each warehouse is routed independently so vehicles stay stationed at their assigned depot.

---

## 5. Dispatch Lifecycle & Persistence (Phase 4B)

Four relational tables persist dispatch execution without modifying live `inventory` or `demands`:

- `dispatch_plans` — Top-level plan referencing `optimization_runs.id`.
- `vehicle_assignments` — Per-vehicle closed tour, payload utilization, distance, and route coordinates.
- `delivery_stops` — Ordered hospital stops (`stop_sequence = 1, 2, ...`) with leg distance and estimated arrival time.
- `shipment_lines` — Product-level `quantity_planned` vs. `quantity_delivered` (initialized strictly to `0.0`).

### Valid State Machine Transitions

| Current Status | Allowed Next Statuses |
| :--- | :--- |
| `planned` | `dispatched`, `cancelled` |
| `dispatched` | `in_transit`, `partially_delivered`, `delivered`, `cancelled` |
| `in_transit` | `partially_delivered`, `delivered`, `cancelled` |
| `partially_delivered` | `in_transit`, `delivered`, `cancelled` |
| `delivered` | *(Terminal — no further transitions)* |
| `cancelled` | *(Terminal — no further transitions)* |

Updating an individual `DeliveryStop` rolls up parent `VehicleAssignment` and `DispatchPlan` statuses (`partially_delivered` when some stops complete; `delivered` when all complete). Invalid transitions return HTTP `422`.

---

## 6. Disaster & Disruption Scenario Simulation Architecture (Phase 4C)

Implemented in `backend/app/simulation/scenario_engine.py` and `backend/app/services/scenario_service.py`:

- **Supported Disruption Types**:
  1. `warehouse_outage` — Disables selected warehouses' supply and home fleets.
  2. `road_closure` — Blocks selected road corridors in both Phase 3 LP (`A_ij = 0`) and Phase 4A OR-Tools VRP.
  3. `demand_spike` — Increases demand by a configurable percentage (`0%–300%`) at selected hospitals (or network-wide).
  4. `vehicle_unavailability` — Removes selected vehicles from the available routing fleet.
  5. `combined` — Applies any combination simultaneously.
- **Zero Live Mutation**: All disruptions operate strictly on read-only in-memory snapshots. Live `warehouses`, `inventory`, `demands`, `roads`, `vehicles`, and baseline `optimization_runs` remain completely unchanged.
- **Persistence**: Every run persists an immutable `ScenarioRun` (`scenario_runs` table) containing exact disruption parameters, baseline KPIs, disrupted KPIs, deltas, and map route/closure overlays.

---

## 7. Baseline vs. Disrupted Comparison KPIs

Every simulation calculates and compares:
1. Original Total Demand vs. Disrupted Total Demand
2. Total Allocated Quantity
3. Unmet Demand
4. Critical-Priority Fulfillment (%)
5. High-Priority Fulfillment (%)
6. Normal-Priority Fulfillment (%)
7. Total Transportation Cost (INR)
8. Total Estimated Route Distance (km)
9. Number of Available Vehicles
10. Number of Completed Feasible Vehicle Routes

---

## 8. Phase 4 API Endpoints

- `GET /api/routes/vehicles` — List fleet vehicles and availability.
- `POST /api/routes/dispatch-plans` (alias `POST /api/routes/vrp`) — Generate and persist OR-Tools CVRP dispatch plan from an `optimization_run_id`.
- `GET /api/routes/dispatch-plans` — List dispatch plan history.
- `GET /api/routes/dispatch-plans/{plan_id}` — Full dispatch plan details.
- `PATCH /api/routes/dispatch-plans/{plan_id}/status` — Update plan lifecycle status.
- `PATCH /api/routes/stops/{stop_id}/status` — Update hospital delivery stop status and delivered quantities.
- `POST /api/scenarios/simulate` — Create and run a disaster scenario simulation.
- `POST /api/scenarios/{scenario_id}/simulate` — Execute a saved scenario definition.
- `GET /api/scenarios/runs` — List scenario simulation history.
- `GET /api/scenarios/runs/{simulation_id}` — Full scenario simulation comparison details.

---

## 9. Testing Results

- **Original Phase 4 Verification**: All 5 Phase 4 test suites (`test_phase4_routing_dispatch_scenarios.py`) verified multi-stop routing, capacity limits, unavailable vehicle exclusion, multi-depot separation, closed road infeasibility, dispatch persistence, exact LP quantity conservation, lifecycle transition rejection, all 5 disaster scenario types, and zero live database mutation.
- **Current Cumulative Regression Suite (Phases 1–6)**: **`37/37` backend tests passing** (`backend\.venv\Scripts\pytest.exe -v`) with `0` failures and `0` skipped tests.

---

## 10. Phase 5 Stage 3 Upgrades & Known Limitations

### Phase 5 Stage 3 Integration Upgrades (Implemented)

- **Real OpenStreetMap Road Geometry & Directed Matrices**: When `data/processed/pune_osm_road_graph.json` is cached and validated, OR-Tools CVRP now replaces Haversine-tortuosity estimates with directed OSM shortest-path road distances (`DISTANCE_SCALE = 1000` meters) or estimated road travel times (`TIME_SCALE = 60` seconds), honoring one-way rules, medical-truck access restrictions, and OSM `closed_way_ids`. See [Phase 5 OSM Routing Documentation](phase5_osm_routing_integration.md).
- **Configurable Routing Objective**: Dispatch plans and disaster scenarios accept `routing_objective: "min_distance" | "min_time"` (default `min_distance`) and always return both actual road distance and estimated travel time.
- **Persistent Route Geometry**: `vehicle_assignments.route_geometry_json` persists ordered OSM street polylines, `osm_way_ids`, and `road_names` via an idempotent additive migration without modifying historical Phase 4 rows.
- **Graceful Synthetic Fallback**: If the OSM cache is missing or invalid, MEDILOGIX automatically falls back to the Phase 4 synthetic corridor + Haversine-tortuosity engine (`routing_source = "synthetic_fallback"`) with explicit warnings.

### Remaining Limitations

- **1D Weight Capacity Only**: Payload limits are weight-based (`kg`); volumetric (cubic meter) and cold-chain compartment constraints are not yet modeled.
- **Assumed Speed-Profile Travel Times**: While road distances and map polylines follow real OpenStreetMap streets (`© OpenStreetMap contributors`, ODbL 1.0), travel times are calculated from assumed urban road-class speed profiles and do **not** represent live traffic, turn-by-turn signal delays, or real-time GPS vehicle tracking.
- **Manual Inventory Deduction**: Marking a delivery stop as `delivered` tracks physical delivery confirmation inside `shipment_lines` without automatically mutating warehouse `inventory` stock levels.
