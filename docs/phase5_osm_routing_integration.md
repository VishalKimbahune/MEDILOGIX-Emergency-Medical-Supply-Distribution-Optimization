# MEDILOGIX — Phase 5 Technical Documentation: OpenStreetMap Road Network & OR-Tools Integration

> **Data & Licensing Attribution**: Road geometry and street metadata are sourced from OpenStreetMap — **© OpenStreetMap contributors (ODbL 1.0)**.
>
> **Travel-Time Honesty Notice**: Road distances and map polylines reflect real OpenStreetMap street geometry. Travel times are **estimated** using assumed urban delivery speed profiles by OSM highway classification and do **not** represent live traffic, congestion telemetry, or guaranteed arrival times.

---

## 1. Architecture Overview (Stages 2 & 3)

Phase 5 upgrades MEDILOGIX from synthetic straight-line corridors to a real-world directed street graph for **Pune and Pimpri-Chinchwad**, tightly integrated with Google OR-Tools CVRP, dispatch persistence, disaster simulation, and the React Leaflet delivery map:

1. **OSM Ingestion & Local Caching (`backend/app/optimization/osm_road_network.py`, `data/fetch_osm_network.py`)**:
   - Queries Overpass API once using the lightweight `out body; >; out skel qt;` pattern over bounding box `lat 18.40..18.70, lon 73.70..74.05` for drivable arterial/collector classes (`motorway`, `trunk`, `primary`, `secondary`, `tertiary`, and `*_link`s).
   - Splits ways at street intersections into a directed `networkx.MultiDiGraph` keyed by `osm_way_id`, preserving parallel streets/flyovers, curved street polyline geometry, geodesic segment lengths, one-way rules (`oneway=yes|-1`, `motorway`, `junction=roundabout`), and delivery/HGV vehicle access restrictions (`access`, `motor_vehicle`, `vehicle`, `hgv`).
   - Persists the validated graph to `data/processed/pune_osm_road_graph.json` (~7.77 MB, `8,716` intersection nodes, `14,933` directed edges, `8,517` one-way edges, `8,611` main SCC nodes) with process-level mtime-checked in-memory caching to avoid redundant disk reads or Overpass calls.

2. **Directed Shortest-Path & All-Pairs Matrix Construction (`build_osm_distance_time_matrix`)**:
   - Snaps each active warehouse and hospital coordinate to the nearest node in the largest Strongly Connected Component (`max_snap_distance_km = 2.5 km`).
   - Filters closed OSM ways (`closed_way_ids`), inaccessible segments (`vehicle_accessible=False`), and HGV-restricted roads (`hgv_restricted=True` for `medical_truck`) using an isolated read-only `nx.subgraph_view` (never mutating the cached graph; bypasses view overhead when no restrictions/closures are active).
   - Runs one `nx.single_source_dijkstra` pass per unique facility to compute asymmetric directed distance (`km`), estimated travel time (`min`), `osm_way_ids`, `road_names`, and street polyline `geometry` for every ordered facility pair.
   - Any unreachable pair or unsnapped facility is explicitly marked `reachable=False` and **never** silently replaced by a synthetic distance while in OSM mode.

3. **Google OR-Tools CVRP Objective & Constraints (`backend/app/optimization/vehicle_routing.py`)**:
   - Supports configurable `routing_objective`:
     - `min_distance` *(default)*: Integer arc costs scaled to meters (`DISTANCE_SCALE = 1000`, fixed vehicle dispatch cost `500`).
     - `min_time`: Integer arc costs scaled to seconds (`TIME_SCALE = 60`, fixed vehicle dispatch cost `120`).
   - Always computes and returns **both** total actual road distance (`route_distance_km`) and total estimated travel time (`estimated_duration_min`).
   - Explicitly forbids unreachable directed arcs between stops via `routing.NextVar(from_idx).RemoveValue(to_idx)`.
   - Preserves strict per-depot separation, 1D weight-based payload capacity (`kg`), split-load handling, multi-wave trips, and exact 100% LP-to-VRP shipment conservation for all routable hospitals.
   - If road closures or snapping make a hospital unreachable from its depot, reports it in `unreachable_hospitals` and `unreachable_connections` with `solver_status = "Partial"` (or `"Infeasible"` if no hospital is routable) instead of fabricating a route.

4. **Road Closure Handling & Isolated Disaster Simulation**:
   - Supports both Phase 4 synthetic corridor closures (`closed_route_codes`) and Phase 5 OSM street closures (`closed_way_ids`) in both `POST /api/routes/dispatch-plans` and `POST /api/scenarios/simulate`.
   - Extracts polyline segments of closed OSM ways (`closed_osm_ways`) for visual rendering on the delivery map.
   - Scenario simulations evaluate closures on isolated in-memory graph views and snapshots, guaranteeing **zero mutation** of live `roads`, `inventory`, `demands`, `vehicles`, or the cached OSM JSON file.

5. **Additive Database Persistence (`backend/app/database/migrations.py`, `backend/app/models/dispatch.py`)**:
   - Adds a nullable JSON column `vehicle_assignments.route_geometry_json` storing `routing_source`, `routing_objective`, ordered `geometry` (`[[lat, lon], ...]`), `way_ids`, `road_names`, per-leg breakdown, and attribution.
   - Stores plan-level `routing_source`, `routing_objective`, `closed_way_ids`, `closed_osm_ways`, `unreachable_hospitals`, `unreachable_connections`, `fallback_warning`, `attribution`, and `travel_time_disclaimer` inside `dispatch_plans.summary_json`.
   - Applies `ALTER TABLE vehicle_assignments ADD COLUMN route_geometry_json JSON` automatically and idempotently on existing SQLite databases without resetting tables or altering historical Phase 4 rows (historical rows with `NULL` gracefully synthesize fallback coordinates on read).

6. **Graceful Offline Synthetic Fallback**:
   - Before every VRP solve, `validate_osm_graph()` verifies graph type, non-empty nodes/edges, valid WGS84 coordinates, and positive finite weights.
   - If the local OSM cache is missing, malformed, or fails validation, MEDILOGIX automatically switches to `routing_source = "synthetic_fallback"`, emits a clear `fallback_warning`, and renders dashed fallback lines on the interactive map.

7. **Interactive React Leaflet Delivery Map & Routing Controls**:
   - [PuneNetworkMap.jsx](file:///d:/MEDILOGIX-%20Optimize%20Medical%20Supply%20Distribution/frontend/src/components/maps/PuneNetworkMap.jsx) uses `preferCanvas={true}` to render smooth curved OSM road polylines per vehicle assignment, numbered stop badges, dashed crimson closed OSM street segments, unreachable hospital halo alerts, routing source/objective badges, and ODbL 1.0 attribution + speed-profile disclaimers.
   - [Routes.jsx](file:///d:/MEDILOGIX-%20Optimize%20Medical%20Supply%20Distribution/frontend/src/pages/Routes.jsx) exposes the **Routing Objective** selector (`Minimum Road Distance` / `Minimum Estimated Travel Time`), optional **Closed OSM Way IDs** input, live OSM graph status indicator, and complete dispatch plan metadata while keeping the existing dispatch lifecycle untouched.
