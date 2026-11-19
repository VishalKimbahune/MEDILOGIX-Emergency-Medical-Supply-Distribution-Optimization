# MEDILOGIX — API Documentation

Base URL (local development): `http://127.0.0.1:8000`  
Interactive OpenAPI / Swagger UI: `http://127.0.0.1:8000/docs`

---

## 1. System Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Returns backend service status, application metadata, configured geographical region, and database connectivity status. |

## 2. Core Resource CRUD Endpoints

| Module | Base Path | Supported Methods |
| :--- | :--- | :--- |
| Warehouses | `/api/warehouses` | `GET /`, `GET /{warehouse_id}`, `POST /`, `PUT /{warehouse_id}`, `DELETE /{warehouse_id}` (returns `409 Conflict` if dependent records exist) |
| Hospitals | `/api/hospitals` | `GET /?priority_level=&area=`, `GET /{hospital_id}`, `POST /`, `PUT /{hospital_id}`, `DELETE /{hospital_id}` (returns `409 Conflict` if dependent records exist) |
| Products | `/api/products` | `GET /`, `GET /{product_id}`, `POST /`, `PUT /{product_id}`, `DELETE /{product_id}` |
| Inventory | `/api/inventory` | `GET /?warehouse_id=&product_id=`, `GET /{inventory_id}`, `POST /`, `PUT /{inventory_id}`, `DELETE /{inventory_id}` |
| Demands | `/api/demands` | `GET /?hospital_id=&product_id=&priority_level=&status=`, `GET /{demand_id}`, `POST /`, `PUT /{demand_id}`, `DELETE /{demand_id}` |

## 3. Operations Research Optimization Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/optimization/transportation` | `POST` | Execute & persist Multi-Commodity Transportation LP (`PuLP CBC`). |
| `/api/optimization/priority` | `POST` | Execute & persist 4-Stage Sequential Lexicographic Priority Optimization (`PuLP CBC`). |
| `/api/optimization/compare` | `POST` | Execute both models on the same dataset, persist both runs, and return side-by-side trade-off metrics. |
| `/api/optimization/runs` | `GET` | List historical optimization runs ordered most recent first. |
| `/api/optimization/runs/{run_id}` | `GET` | Retrieve full immutable details (allocations, priority summary, warehouse utilization, product/hospital summaries, stage results, formulation explanation) for a historical run. |
| `/api/optimization/latest-allocations` | `GET` | Aggregate allocated quantities per `(hospital_id, product_id)` from the most recent optimization run. |

### Sample Optimization Request (`POST /api/optimization/priority`)

```json
{
  "model_type": "lexicographic_priority",
  "warehouse_codes": null,
  "hospital_codes": null,
  "product_codes": null,
  "scenario_id": null,
  "enforce_route_availability": true,
  "allow_unmet_demand": true
}
```

### Sample Optimization Response (Abbreviated)

```json
{
  "id": 2,
  "run_code": "RUN-20261118072839-032AAF",
  "executed_at": "2026-11-18T07:28:39.104512Z",
  "model_type": "lexicographic_priority",
  "solver_name": "PuLP CBC (COIN-OR Branch and Cut)",
  "solver_status": "Optimal",
  "is_planned_allocation": true,
  "total_cost": 144463.31,
  "total_demand": 2611.0,
  "total_allocated": 2422.0,
  "total_unmet_demand": 189.0,
  "fulfillment_percentage": 92.76,
  "tier_unmet_fractions": {
    "critical": 0.0,
    "high": 0.012859,
    "normal": 0.256186
  },
  "priority_summary": [
    {
      "priority_level": "critical",
      "hospital_count": 2,
      "total_demand": 913.0,
      "total_allocated": 913.0,
      "total_unmet": 0.0,
      "unmet_fraction": 0.0,
      "fulfillment_pct": 100.0
    }
  ],
  "stage_results": [
    {
      "stage": 1,
      "name": "Stage 1: Minimize Critical Hospital Normalized Unmet Demand",
      "priority_tier": "critical",
      "objective_metric": "critical_unmet_fraction",
      "objective_value": 0.0,
      "tier_demand": 913.0,
      "solver_status": "Optimal",
      "execution_time_ms": 70.3,
      "skipped": false
    }
  ],
  "warehouse_utilization": [],
  "product_summary": [],
  "hospital_summary": [],
  "allocations": [],
  "unmet_demands": [],
  "formulation_summary": {
    "model_title": "4-Stage Lexicographic Priority Shortage Optimization",
    "solver": "PuLP CBC (COIN-OR Branch and Cut)"
  },
  "execution_time_ms": 306.12
}
```

## 4. Routing, OpenStreetMap Road Network, Dispatch Management, Scenarios & Analytics Endpoints

| Module | Endpoint | Method | Description |
| :--- | :--- | :--- | :--- |
| Routes | `/api/routes` | `GET` | List warehouse-hospital synthetic road corridors with coordinates and estimates. |
| Routes | `/api/routes/vehicles` | `GET` | List fleet vehicles with warehouse assignment, weight capacity, and availability status. |
| Routes | `/api/routes/shortest-path` | `POST` | Compute shortest path on the synthetic corridor graph via NetworkX Dijkstra. |
| OSM Network | `/api/routes/road-network/status` | `GET` | Report cached Pune/PCMC OSM road-graph metrics, `© OpenStreetMap contributors (ODbL 1.0)` attribution, active routing source, and facility snapping status. |
| OSM Network | `/api/routes/road-network/sync` | `POST` | Download (if uncached or `force_refresh: true`) and locally cache the Pune/PCMC OSM directed street graph with graceful offline fallback. |
| OSM Network | `/api/routes/road-network/shortest-path` | `POST` | Compute directed shortest path between two facilities over cached OSM street geometry respecting one-way rules, vehicle access, and `closed_way_ids` (with automatic synthetic fallback if uncached). |
| Dispatch | `/api/routes/dispatch-plans` | `POST` | Generate and persist a Google OR-Tools multi-depot CVRP dispatch plan using cached OSM road distances/estimated times (or synthetic fallback). Supports `routing_objective` (`min_distance` \| `min_time`) and `closed_way_ids` (alias: `POST /api/routes/vrp`). |
| Dispatch | `/api/routes/dispatch-plans` | `GET` | List historical dispatch plans with `routing_source` and `routing_objective`. |
| Dispatch | `/api/routes/dispatch-plans/{plan_id}` | `GET` | Retrieve full dispatch plan details including ordered `route_geometry`, `osm_way_ids`, `road_names`, `closed_osm_ways`, `unreachable_hospitals`, `fallback_warning`, `attribution`, and `travel_time_disclaimer`. |
| Dispatch | `/api/routes/dispatch-plans/{plan_id}/status` | `PATCH` | Transition dispatch plan status (`planned` → `dispatched` → `in_transit` → `partially_delivered` / `delivered` / `cancelled`). |
| Dispatch | `/api/routes/stops/{stop_id}/status` | `PATCH` | Update individual hospital delivery stop status and delivered quantities. |
| Scenarios | `/api/scenarios` | `GET`, `POST`, `DELETE /{id}` | Manage saved disaster scenario definitions. |
| Scenarios | `/api/scenarios/simulate` | `POST` | Create and execute an isolated disaster simulation (warehouse outage, corridor closure, OSM `closed_way_ids`, demand spike, vehicle unavailability, or combined) without mutating live DB or OSM cache. |
| Scenarios | `/api/scenarios/{scenario_id}/simulate` | `POST` | Execute a saved scenario definition against a baseline optimization run. |
| Scenarios | `/api/scenarios/runs` | `GET` | List persisted scenario simulation history. |
| Scenarios | `/api/scenarios/runs/{simulation_id}` | `GET` | Retrieve full baseline-vs-disrupted comparison KPIs, recalculated OSM/fallback routes (`route_geometry`, `osm_way_ids`), `closed_corridors`, `closed_osm_ways`, and `unreachable_hospitals`. |
| Analytics | `/api/analytics/summary` | `GET` | Aggregate live database KPIs and latest optimization run cost/fulfillment. |
| Analytics | `/api/analytics/supply-demand-gap` | `GET` | Product-wise supply vs. actionable demand comparison. |
| Analytics | `/api/analytics/overview` | `GET` | Comprehensive Phase 6 analytics across Supply Chain (live), Optimization (historical snapshot), Dispatch & Fleet, and Disaster Scenarios. |

### Sample Dispatch Plan Request (`POST /api/routes/dispatch-plans`)

```json
{
  "optimization_run_id": 2,
  "routing_objective": "min_distance",
  "closed_way_ids": [],
  "closed_route_codes": [],
  "disabled_vehicle_codes": [],
  "allow_multi_trip": true,
  "max_trips_per_vehicle": 3,
  "allow_split_deliveries": true
}
```

### Sample Dispatch Plan Response (Abbreviated, OSM Mode)

```json
{
  "id": 2,
  "plan_code": "DSP-20261118125500-A1B2C3",
  "optimization_run_id": 2,
  "optimization_run_code": "RUN-20261118072839-032AAF",
  "status": "planned",
  "solver_status": "Optimal",
  "routing_source": "osm",
  "routing_objective": "min_distance",
  "total_vehicles_used": 6,
  "total_routes": 6,
  "total_stops": 10,
  "total_distance_km": 118.42,
  "estimated_duration_min": 214.6,
  "total_weight_kg": 18250.5,
  "closed_way_ids": [],
  "closed_osm_ways": [],
  "unreachable_hospitals": [],
  "unreachable_connections": [],
  "fallback_warning": null,
  "attribution": "© OpenStreetMap contributors (ODbL 1.0)",
  "travel_time_disclaimer": "Estimated travel times are based on assumed road-class speed profiles and do NOT represent live traffic or guaranteed arrival times.",
  "vehicle_assignments": [
    {
      "id": 7,
      "vehicle_code": "VEH-WH-01-01",
      "vehicle_type": "medical_truck",
      "warehouse_code": "WH-01",
      "trip_number": 1,
      "status": "planned",
      "total_load_kg": 3420.0,
      "capacity_kg": 4000.0,
      "utilization_pct": 85.5,
      "route_distance_km": 31.48,
      "estimated_duration_min": 52.3,
      "routing_source": "osm",
      "routing_objective": "min_distance",
      "route_geometry": [[18.6298, 73.7997], [18.631036, 73.80157]],
      "osm_way_ids": [210788741, 40581234],
      "road_names": ["Old Pune–Mumbai Highway", "University Road"],
      "delivery_stops": []
    }
  ]
}
```
