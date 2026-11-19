# MEDILOGIX — B.Tech Viva Questions and Answers (45 Questions)

---

## A. Operations Research & Linear Programming

**1. What is Operations Research (OR), and why is it suitable for emergency medical supply distribution?**  
Operations Research applies mathematical modeling and optimization algorithms to allocate scarce resources under constraints. During medical emergencies, demand exceeds supply across geographically dispersed hospitals, making mathematical optimization far more reliable and auditable than manual heuristics.

**2. Why is the MEDILOGIX allocation model formulated as a Linear Program (LP)?**  
All objective terms (total unmet demand, normalized priority unmet fractions, and transportation cost) and all constraints (warehouse supply ceilings, hospital demand balance, route availability) are linear in the continuous decision variables $x_{i,j,k}$ and $u_{j,k}$, allowing polynomial/simplex-efficient global optimality via PuLP and COIN-OR CBC.

**3. What are the decision variables in the allocation LP?**  
$x_{i,j,k} \ge 0$ represents the planned quantity of medical product $k$ shipped from warehouse $i$ to hospital $j$ on an open corridor $(i,j)$, and $u_{j,k} \ge 0$ represents the unmet demand (shortage) of product $k$ at hospital $j$.

**4. Explain the warehouse supply constraint and hospital demand balance constraint.**  
Warehouse supply: $\sum_j x_{i,j,k} \le S_{i,k}$ ensures a warehouse never ships more than its net available stock (`quantity_available - quantity_reserved`). Hospital demand balance: $\sum_i x_{i,j,k} + u_{j,k} = D_{j,k}$ ensures every requested unit is either allocated or explicitly accounted for as unmet shortage.

**5. Why do you include slack/unmet variables $u_{j,k}$ instead of strict equality $\sum_i x_{i,j,k} = D_{j,k}$?**  
During controlled shortages or warehouse outages, total supply is less than total demand. Without $u_{j,k}$, the LP becomes immediately infeasible and provides no actionable distribution plan. With $u_{j,k} \ge 0$, the solver allocates all feasible supply optimally while quantifying exact shortages.

**6. Are the continuous LP decision variables $x_{i,j,k}$ guaranteed to be integers?**  
Not universally. While pure single-commodity transportation LPs with integer supplies and demands satisfy total unimodularity, introducing multi-commodity side constraints (like route weight capacity or normalized tier-fraction bounds) can break total unimodularity. MEDILOGIX explicitly documents this and avoids blanket integrality claims.

**7. What solver does PuLP use in MEDILOGIX?**  
COIN-OR CBC (`PULP_CBC_CMD(msg=False, threads=1)`), an open-source, deterministic linear and mixed-integer programming solver.

---

## B. Transportation Problem & Lexicographic Optimization

**8. How does a multi-commodity transportation problem differ from a classical single-commodity transportation problem?**  
In a single-commodity problem, all units are interchangeable. In MEDILOGIX, 4 distinct medical products (Oxygen Cylinders, IV Fluids, Trauma Kits, Essential Medicines) have separate warehouse stocks, separate hospital demands, and product-specific unit transport costs and weights.

**9. What limitation of pure cost-minimizing Transportation LP did MEDILOGIX observe?**  
On the `seed=42` baseline dataset, pure Transportation LP achieved ₹134,932.40 cost but left **76 Critical-priority** and **108 High-priority** units unmet while fulfilling **99.27%** of cheaper Normal-priority hospitals.

**10. What is Lexicographic Multi-Objective Optimization?**  
It solves a strict hierarchy of objectives sequentially: the highest-priority objective is optimized first, its optimal value is locked as a constraint, and only then is the next-priority objective optimized over the remaining feasible space.

**11. Why did you use 4-stage sequential lexicographic optimization instead of a single big-M weighted objective?**  
Big-M penalty weights are arbitrary, sensitive to scaling/units, and can cause numerical instability or unintended trade-offs when transport costs vary widely. Sequential lexicographic locking mathematically guarantees that no amount of cost savings can sacrifice even a single unit of Critical-tier fulfillment.

**12. Why do you normalize unmet demand by total tier demand $F_P = \sum u_{j,k} / D_P$ in each lexicographic stage?**  
Normalization expresses each tier's shortage on a dimensionless $[0, 1]$ scale (making fulfillment percentages directly interpretable) and ensures numerical consistency across stages. When a tier has zero demand ($D_P = 0$), the stage is cleanly skipped to avoid division by zero.

**13. What was the verified trade-off between Transportation LP and Lexicographic Priority LP on the seeded dataset?**  
Lexicographic Priority LP raised Critical fulfillment from **91.68% to 100.00%** (`0` unmet) and High fulfillment from **89.32% to 98.71%**, for a **+7.06%** transport cost increase (₹134,932.40 → ₹144,463.31).

**14. What happens if a hospital's corridors are all closed?**  
Because `x[i,j,k]` variables are only created for open corridors $(i,j) \in A$, closed corridors strictly carry zero flow, and the hospital's demand appears transparently in `unmet_demands`.

---

## C. Vehicle Routing (VRP / CVRP) & Google OR-Tools

**15. Why did you decouple LP allocation (Phase 3) from Vehicle Routing (Phase 4–5)?**  
Combining multi-commodity allocation and capacitated multi-depot VRP into a single MILP is NP-hard and scales poorly. Decoupling lets PuLP solve allocation globally to optimality in milliseconds, and Google OR-Tools route the exact resulting shipments per depot while guaranteeing 100% shipment conservation.

**16. What is CVRP, and how is Multi-Depot CVRP handled in MEDILOGIX?**  
CVRP (Capacitated Vehicle Routing Problem) finds minimum-cost closed tours for capacity-constrained vehicles visiting customer stops. MEDILOGIX groups Phase 3 allocations by origin warehouse and solves an independent depot-based CVRP per warehouse so vehicles never mix depot origins.

**17. How does Google OR-Tools enforce vehicle payload capacities?**  
Weights are scaled by `WEIGHT_SCALE = 10` (0.1 kg integer precision) and enforced with `routing.AddDimensionWithVehicleCapacity(..., slack_max=0, fix_start_cumul_to_zero=True, name="Capacity")`. A post-solve assertion verifies `route_load <= capacity_kg` on every route.

**18. What first-solution heuristic and metaheuristic does OR-Tools use in MEDILOGIX?**  
`PATH_CHEAPEST_ARC` builds an initial feasible tour, and `GUIDED_LOCAL_SEARCH` escapes local minima within a configurable time limit and solution limit.

**19. How does MEDILOGIX handle a hospital shipment heavier than the depot's largest truck?**  
When `allow_split_deliveries=True`, `_split_oversized_stop()` splits the hospital's shipment lines into capacity-feasible sub-stops while conserving exact unit counts. When disabled, it cleanly reports infeasibility (`422`).

**20. How do multi-wave trips work, and how are wave numbers assigned?**  
When `allow_multi_trip=True`, each available vehicle is given up to `max_trips_per_vehicle` closed-tour slots. After solving, active tours per vehicle are normalized sequentially (`Wave #1, Wave #2, ...`).

**21. Why does MEDILOGIX use integer scaling (`DISTANCE_SCALE = 1000`, `TIME_SCALE = 60`) in OR-Tools?**  
Google OR-Tools' C++ routing solver operates strictly on 64-bit integers. Scaling km to meters (`×1000`) and minutes to seconds (`×60`) preserves fine precision without truncation distortion.

**22. How does the `min_distance` vs. `min_time` routing objective work?**  
In `min_distance` mode, OR-Tools minimizes total directed road meters; in `min_time` mode, it minimizes total estimated travel seconds based on road-class speed profiles. Both total distance and estimated duration are always returned regardless of the chosen objective.

---

## D. OpenStreetMap, NetworkX & Graph Algorithms

**23. Why did you choose NetworkX `MultiDiGraph` over a simple `DiGraph` for OSM roads?**  
A simple `DiGraph` allows at most one directed edge between two intersections, overwriting alternate parallel roads (such as flyovers vs. service roads). A `MultiDiGraph` keyed by `osm_way_id` preserves all parallel streets so closing one OSM way allows Dijkstra to reroute onto open parallel roads.

**24. How are OSM one-way roads and vehicle access restrictions handled?**  
`parse_overpass_to_digraph()` inspects `oneway`, `motorway`, and `junction=roundabout` tags to create directed edges only in legal directions, and excludes `footway`, `cycleway`, `access=private/no`, `motor_vehicle=no`, and `hgv=no` (for `medical_truck`). Dynamic edge filtering also checks `vehicle_accessible` and `hgv_restricted`.

**25. What is a Strongly Connected Component (SCC), and why do you snap facilities to the largest SCC?**  
In a directed graph, every node in an SCC can reach every other node and return. Snapping warehouses and hospitals to the largest SCC (`8,611 / 8,716` nodes, `98.8%` in Pune/PCMC) prevents snapping onto one-way dead-end stubs where a truck could arrive but never return to its depot.

**26. How do you compute the all-pairs facility distance/time matrix efficiently on an 8,716-node graph?**  
Instead of calling pairwise Dijkstra $N(N-1)$ times, `build_osm_distance_time_matrix()` runs `nx.single_source_dijkstra` once per unique facility (~11 runs total), reconstructing exact distances, estimated times, `way_ids`, and curved polylines in a fraction of a second.

**27. Why do you cache the OSM graph locally in JSON instead of calling Overpass on every route request?**  
Public Overpass API servers enforce strict fair-use rate limits and can experience latency or timeouts. Local caching in `data/processed/pune_osm_road_graph.json` makes routing fast, deterministic, polite to OSM infrastructure, and completely functional offline.

**28. What happens if the local OSM cache is missing or corrupted?**  
`validate_osm_graph()` detects missing, malformed, or empty graphs and activates `synthetic_fallback` cleanly with a clear `fallback_warning` in both API responses and UI banners—never crashing dispatch generation.

**29. What happens in OSM mode if a single hospital becomes unreachable due to an OSM road closure?**  
MEDILOGIX never silently substitutes a synthetic distance for an unreachable leg in OSM mode. It marks the connection unavailable, forbids unreachable arcs in OR-Tools, reports the hospital in `unreachable_hospitals`, and marks the plan `Partial` (or `Infeasible` if no stops remain routable).

**30. Are MEDILOGIX travel times real-time traffic?**  
No. Road geometry and distances come from OpenStreetMap (`© OpenStreetMap contributors, ODbL 1.0`), whereas travel times are calculated from assumed urban speed profiles by OSM highway class. Every API response, map footer, and UI screen explicitly disclaims this.

---

## E. Full-Stack Engineering (FastAPI, React, Database)

**31. Why FastAPI instead of Flask or Django for MEDILOGIX?**  
FastAPI provides native Pydantic v2 request/response validation, automatic OpenAPI/Swagger documentation (`/docs`), clean dependency injection for database sessions, and high performance for RESTful OR microservices.

**32. How do you prevent invalid dispatch status jumps (e.g., `planned` directly to `delivered`)?**  
`VALID_TRANSITIONS` defines an explicit directed state machine in `dispatch_service.py`. Any disallowed transition raises `DispatchDomainError(status_code=422)`, and individual stop updates automatically roll up parent assignment and plan statuses.

**33. Why doesn't generating a dispatch plan automatically mark shipments as delivered or deduct live warehouse stock?**  
Generating a route is a *planning* decision, not a physical warehouse handover. Initializing `status='planned'` and `quantity_delivered=0.0` preserves operational truthfulness and allows tracking partial or full physical deliveries separately.

**34. How do you ensure disaster simulations never corrupt live database tables or the OSM cache?**  
`scenario_service.py` snapshots live operational tables into pure Python in-memory dataclasses and applies OSM `closed_way_ids` via read-only `nx.subgraph_view` filters. Only an immutable `ScenarioRun` record is persisted; automated tests assert exact before/after equality of live inventory, demands, roads, vehicles, baseline runs, and cache file bytes.

**35. How did you add `route_geometry_json` to `vehicle_assignments` without resetting existing SQLite data?**  
An idempotent additive migration (`backend/app/database/migrations.py`) inspects existing table columns at startup and executes `ALTER TABLE vehicle_assignments ADD COLUMN route_geometry_json JSON` only if absent, leaving all historical rows untouched.

**36. Why did you enable `preferCanvas={true}` on the React Leaflet `MapContainer`?**  
Multi-stop OSM routes contain hundreds to thousands of curved polyline vertices. Rendering polylines on HTML5 Canvas rather than individual DOM SVG nodes keeps panning, zooming, and filtering smooth across desktop and mobile devices.

**37. How are foreign-key constraints enforced in SQLite?**  
SQLite disables foreign keys by default. MEDILOGIX registers a SQLAlchemy engine `connect` event listener that executes `PRAGMA foreign_keys=ON` on every connection, and DELETE endpoints return `409 Conflict` when dependent rows exist.

**38. Why does the Analytics dashboard separate Live Operational KPIs from Historical Optimization Snapshot KPIs?**  
During Phase 4's integration audit, comparing live open demand (`2,359` units after user edits) against a historical run snapshot (`1,844` or `2,517` units) caused confusion when unlabeled. Separating live operational metrics from immutable run snapshots eliminates denominator mismatches and guarantees exact KPI consistency.

---

## F. Data Science, Supply Chain Management & Project Design

**39. Why was the synthetic dataset seeded with `RANDOM_SEED = 42`?**  
A fixed random seed guarantees reproducible baseline experiments so any evaluator running `generate_dataset.py` reproduces identical supply shortages, cost trade-offs, and test outcomes.

**40. Why does the synthetic dataset intentionally include a controlled supply shortage (~92.76% coverage)?**  
If supply exceeded demand everywhere, pure cost LP and Lexicographic Priority LP would produce identical 100% fulfillment. A controlled shortage demonstrates the real-world life-safety advantage of lexicographic prioritization.

**41. What is the difference between `open`, `partially_fulfilled`, and `fulfilled` demands in MEDILOGIX?**  
`open` and `partially_fulfilled` together form **Actionable Demand** fed into the optimization engine, whereas `fulfilled` and `cancelled` demands are excluded from new optimization runs.

**42. How is `LP-to-VRP Shipment Conservation` verified?**  
For every `(warehouse_code, hospital_code, product_code)` triplet, automated tests sum `quantity_planned` across all `ShipmentLine` rows in the generated `DispatchPlan` and assert equality (within `0.05` tolerance) to the source `Allocation.quantity_allocated`.

**43. Why are warehouses labeled as "fictional simulation hubs" and hospitals as "synthetic profiles"?**  
Using general Pune & Pimpri-Chinchwad coordinates with explicitly fictional names and synthetic quantities maintains academic and ethical integrity—no real hospital's private stock or emergency data is fabricated or misrepresented.

**44. How easily can MEDILOGIX expand from Pune Urban & PCMC to the entire Pune District or another city?**  
Geographic boundaries (`GEO_MIN_LAT`, `GEO_MAX_LAT`, `GEO_MIN_LON`, `GEO_MAX_LON`, `GEO_REGION_NAME`) are environment variables. Updating `.env`, adding facility records via CRUD, and re-running `fetch_osm_network.py --force` adapts the entire platform without code rewrites.

**45. What are the top three real-world extensions you would build next?**  
(1) **VRPTW** (Vehicle Routing with Time Windows) for urgent critical-care delivery deadlines, (2) **Multi-dimensional capacity** (weight + cubic volume + cold-chain compartment constraints), and (3) **Automated inventory reconciliation** with reservation/deduction approval workflows upon confirmed delivery.
