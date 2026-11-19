# MEDILOGIX — Final B.Tech Project Presentation (15 Slides)

---

## Slide 1: Title Slide
- **Title**: **MEDILOGIX** — Emergency Medical Supply Distribution Optimization Using Operations Research and Intelligent Decision Support
- **Domain**: Operations Research (OR) · Supply Chain Management (DSCM) · Full-Stack Decision Support
- **Geographic Scope**: Pune Urban Area & Pimpri-Chinchwad, Maharashtra, India
- **Tech Stack**: Python (FastAPI, PuLP CBC, Google OR-Tools, NetworkX, SQLAlchemy) · React (Vite, Tailwind CSS, Recharts, React Leaflet) · OpenStreetMap (ODbL 1.0)

---

## Slide 2: Problem Statement
- During public health emergencies or urban disruptions (monsoon flooding, trauma surges, warehouse outages), medical supply demand often exceeds available stock.
- Manual or purely cost-driven dispatch causes **critical-care trauma centers** farther from depots to suffer life-threatening shortages while lower-priority nearby units are fully stocked.
- Straight-line distance approximations ignore real Pune one-way arterials, truck access limits, and street-level closures.
- Decision-makers need an integrated, mathematically sound platform linking **priority-aware supply allocation**, **capacitated vehicle routing**, **real road geometry**, and **zero-risk disaster stress testing**.

---

## Slide 3: Motivation
- **Lives over pure cost**: Emergency logistics requires formal lexicographic priority guarantees rather than arbitrary ad-hoc weights.
- **Bridging theory and engineering**: Translating classical OR models (Transportation LP, Multi-Objective Lexicographic LP, CVRP, Directed Shortest Path) into a usable, audited web platform.
- **Transparency & explainability**: Every allocation, route, and simulation must remain reproducible, inspectable, and honest about assumptions.

---

## Slide 4: Project Objectives
1. Build a full-stack CRUD management system for warehouses, hospitals, medical inventory, and hospital demand requests.
2. Formulate and solve **Multi-Commodity Transportation LP** and **4-Stage Sequential Lexicographic Priority LP** using PuLP/CBC.
3. Decouple allocation from **Multi-Depot Capacitated Vehicle Routing (CVRP)** via Google OR-Tools with 100% shipment conservation.
4. Integrate real **Pune & Pimpri-Chinchwad OpenStreetMap directed street geometry** with local caching and offline synthetic fallback.
5. Provide an isolated **Disaster & Disruption Scenario Simulator** and dynamic **Analytics & Reports** workbench.

---

## Slide 5: Existing vs. Proposed System
| Aspect | Conventional / Manual Approaches | MEDILOGIX (Proposed System) |
| :--- | :--- | :--- |
| Allocation Logic | Spreadsheet / First-Come-First-Served | PuLP CBC Transportation LP & 4-Stage Lexicographic Priority LP |
| Critical Protection | Arbitrary manual overrides | Strict sequential stage locking (Critical → High → Normal → Cost) |
| Vehicle Routing | Manual assignment / straight lines | Google OR-Tools Multi-Depot CVRP on directed OSM street graph |
| Road Restrictions | Ignored | One-way rules, HGV/truck access limits, OSM `way_id` closures |
| Disruption Testing | Ad-hoc guesswork | Isolated in-memory Scenario Simulator (zero live DB mutation) |
| Auditability | Fragile manual logs | 16-table relational DB with immutable run, dispatch & scenario history |

---

## Slide 6: System Architecture
- **Presentation Layer**: React 18 + Vite + Tailwind CSS + Recharts + React Leaflet (`preferCanvas` curved OSM polylines & interactive layer filters).
- **API Layer**: FastAPI + Pydantic v2 strict validation (`/api/warehouses`, `/hospitals`, `/inventory`, `/demands`, `/optimization`, `/routes`, `/scenarios`, `/analytics`).
- **OR & GIS Engine Layer**:
  - `transportation.py` & `priority.py` (PuLP CBC)
  - `vehicle_routing.py` (Google OR-Tools CVRP)
  - `osm_road_network.py` (NetworkX `MultiDiGraph` + Overpass local JSON cache)
  - `scenario_engine.py` (Isolated disruption engine)
- **Persistence Layer**: SQLAlchemy 2.0 (16 relational tables, SQLite dev / PostgreSQL production-ready, idempotent additive migrations).

---

## Slide 7: Dataset, Geographic Scope & Ethical Assumptions
- **Scope**: Pune Urban & Pimpri-Chinchwad (`lat 18.40–18.70, lon 73.70–74.05`).
- **Reproducible Synthetic Baseline (`RANDOM_SEED = 42`)**:
  - 3 fictional simulation warehouse hubs (`WH-01` Pimpri, `WH-02` Swargate, `WH-03` Wagholi)
  - 8 synthetic hospital profiles (`2` Critical, `3` High, `3` Normal)
  - 4 essential medical products (Oxygen Cylinders, IV Fluid Cartons, Trauma Kits, Essential Medicine Boxes)
  - 6 fleet vehicles (`medical_truck` / `medical_van`), 24 fallback road corridors
- **Real OSM Street Graph**: `8,716` road intersection nodes, `14,933` directed segments (`8,517` one-way), `© OpenStreetMap contributors (ODbL 1.0)`.
- **Transparency**: Travel times use road-class speed-profile estimates — **never** claimed as live traffic or GPS tracking.

---

## Slide 8: Mathematical Optimization Model (Transportation LP)
- **Decision Variables**: $x_{i,j,k} \ge 0$ (planned flow), $u_{j,k} \ge 0$ (unmet demand).
- **Constraints**:
  - Warehouse stock ceiling: $\sum_j x_{i,j,k} \le S_{i,k}$
  - Hospital demand balance: $\sum_i x_{i,j,k} + u_{j,k} = D_{j,k}$
  - Closed corridors strictly blocked: $x_{i,j,k} = 0$ if $(i,j) \notin A$
- **Baseline Result (`seed=42`)**:
  - Total Demand: `2,611` units | Allocated: `2,422` (`92.76%`) | Cost: **₹134,932.40**
  - Critical fulfillment: `91.68%` (`76` unmet), High: `89.32%` (`108` unmet), Normal: `99.27%` (`5` unmet).

---

## Slide 9: 4-Stage Sequential Lexicographic Priority LP
- Avoids fragile big-M scalarization by solving **4 locked stages** over normalized tier unmet fractions $F_P = \sum_{j \in J_P, k} u_{j,k} / D_P$:
  1. Minimize $F_{\text{crit}} \implies F_{\text{crit}}^*$
  2. Minimize $F_{\text{high}}$ subject to locking $F_{\text{crit}}^*$
  3. Minimize $F_{\text{norm}}$ subject to locking $F_{\text{crit}}^*, F_{\text{high}}^*$
  4. Minimize total transportation cost subject to locking all three tiers
- **Verified Trade-Off (`seed=42`)**:
  - Critical fulfillment rises from **91.68% → 100.00% (`0` unmet)**
  - High fulfillment rises from **89.32% → 98.71% (`13` unmet)**
  - Transportation cost increases modestly from **₹134,932.40 → ₹144,463.31 (+7.06%)**

---

## Slide 10: Vehicle Routing & Persistent Dispatch Management
- **Strict LP-to-VRP Decoupling**: OR-Tools CVRP never alters LP quantities — 100% shipment conservation across every `(warehouse, hospital, product)` triplet.
- **Multi-Depot Isolation**: Each warehouse routes only its stationed available vehicles on closed depot-to-depot tours.
- **Constraints & Features**: 1D weight payload capacity (`kg`), automatic split-load chunking, sequential multi-wave trips, configurable objective (**Minimum Road Distance** vs. **Minimum Estimated Travel Time**).
- **Validated Dispatch Lifecycle**: `planned` → `dispatched` → `in_transit` → `partially_delivered` / `delivered` / `cancelled` (new plans initialize at `0` delivered; invalid transitions return HTTP `422`).

---

## Slide 11: Real-World OpenStreetMap Road Integration
- **Local Caching**: Overpass API downloaded once into `data/processed/pune_osm_road_graph.json` (`~7.77 MB`), eliminating repeated API load and enabling offline demos.
- **Directed `MultiDiGraph`**: Preserves parallel roads/flyovers, curved street polylines, one-way directionality, HGV restrictions, and OSM `way_id` road closures.
- **Live Pune Results (on latest optimal run)**:
  - `min_distance`: **164.25 km**, **326.5 min** est. (`920` polyline pts on first route along *Mother Teresa Flyover*, *Chinchwad Road*, etc.)
  - `min_time`: **168.18 km**, **311.6 min** est. (**14.9 min faster** via faster arterials)
- **Graceful Fallback**: Missing or invalid cache automatically activates `synthetic_fallback` with clear UI & API warnings.

---

## Slide 12: Isolated Disaster & Disruption Scenario Simulator
- **5 Disruption Modes**: Warehouse Outage · Corridor & OSM `way_id` Road Closure · Hospital Demand Spike (`0–300%`) · Vehicle Unavailability · Combined Multi-Factor Disruption.
- **Strict Isolation**: Runs on in-memory operational snapshots and read-only OSM `subgraph_view` — **zero mutation** of live inventory, demands, roads, vehicles, OSM cache, or baseline runs.
- **Output**: 11+ baseline-vs-disrupted comparison KPIs (including route distance & duration deltas), Recharts impact charts, interactive disruption map, and immutable `ScenarioRun` persistence.

---

## Slide 13: Experimental Results & Verification Summary
- **Backend Automated Tests**: **37/37 passed** (`pytest -v`) covering CRUD, dataset validation, Transportation LP, Lexicographic LP, OR-Tools CVRP, dispatch lifecycle, OSM graph parsing/routing/closures/fallback, analytics KPI consistency, and a full 24-step E2E acceptance test.
- **Frontend Production Build**: `npm run build` succeeded cleanly (`2,306` modules compiled via Vite).
- **Live Database Preservation**: All historical runs, dispatch records, and facilities preserved intact via non-destructive additive schema migration.
- *(Presenter note: insert live UI screenshots of Dashboard, Optimization Comparison, OSM Curved Delivery Map, Disaster Simulator, and Analytics & Reports here.)*

---

## Slide 14: Limitations & Future Scope
- **Current Limitations**:
  - 1D weight payload capacity only (cubic volume & cold-chain compartments not yet modeled).
  - Travel times are road-class speed-profile estimates (no real-time traffic or GPS telemetry).
  - Continuous LP variables do not guarantee integrality under arbitrary multi-commodity side constraints.
  - Delivery confirmation tracks `shipment_lines` without auto-deducting warehouse `inventory`.
- **Future Scope**:
  - Vehicle Routing with Time Windows (VRPTW) and multi-dimensional (weight + volume + cold-chain) packing.
  - Stochastic / rolling-horizon demand forecasting and automatic inventory reconciliation workflows.
  - Expansion from Pune Urban & PCMC to full Pune District via environment bounding-box configuration.

---

## Slide 15: Conclusion
- **MEDILOGIX** delivers a complete, mathematically verified, and demonstrable emergency medical supply decision-support platform.
- Combines classical Operations Research (**PuLP CBC**), industrial vehicle routing (**Google OR-Tools**), real street topology (**OpenStreetMap + NetworkX**), and modern web engineering (**FastAPI + React**).
- Ready for academic evaluation, viva defense, and real-world disaster-preparedness demonstration.
- **Thank You — Questions & Live Demo!**
