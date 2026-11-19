# MEDILOGIX — System Architecture

MEDILOGIX follows a decoupled, service-oriented three-tier web architecture with a dedicated **Operations Research, Vehicle Routing, OpenStreetMap Road-Network, and Disaster Simulation Engine** layer.

---

## 1. Overall System Architecture

```mermaid
flowchart TD
    UI["React + Vite SPA (Tailwind CSS, Recharts, React Leaflet)"]
    API["FastAPI REST API Layer (/api/* + Pydantic v2 Validation)"]
    SVC["Domain Services Layer (CRUD, Optimization, Dispatch, Scenarios, Road Network, Analytics)"]
    LP["Allocation Engine: PuLP CBC (Transportation LP & 4-Stage Lexicographic LP)"]
    VRP["Routing Engine: Google OR-Tools Multi-Depot CVRP"]
    OSM["OSM Directed Road Graph Engine (NetworkX MultiDiGraph + Overpass Sync)"]
    SIM["Disaster Scenario Simulator (In-Memory Isolated Snapshots)"]
    DB["SQLAlchemy 2.0 ORM (SQLite Dev / PostgreSQL Prod — 16 Tables)"]
    CACHE["Local OSM Graph Cache (data/processed/pune_osm_road_graph.json)"]
    OVERPASS["OpenStreetMap Overpass API (Explicit Sync Only)"]

    UI -->|REST / JSON over HTTP| API
    API --> SVC
    SVC --> LP
    SVC --> VRP
    SVC --> OSM
    SVC --> SIM
    SVC --> DB
    VRP --> OSM
    SIM --> LP
    SIM --> VRP
    OSM --> CACHE
    OSM -.->|Manual Sync / Fallback if Offline| OVERPASS
```

---

## 2. Backend Request Lifecycle Flow

```mermaid
sequenceDiagram
    participant User as React Frontend
    participant Router as FastAPI Router
    participant Schema as Pydantic v2 Schema
    participant Service as Domain Service
    participant Solver as OR / OSM Engine
    participant DB as SQLAlchemy / SQLite

    User->>Router: HTTP Request (JSON)
    Router->>Schema: Validate types, bounds & enums
    alt Validation Error
        Schema-->>User: HTTP 422 Unprocessable Entity
    else Valid Payload
        Router->>Service: Invoke service with DB session
        Service->>DB: Read operational records / snapshot
        Service->>Solver: Execute LP / OR-Tools VRP / Dijkstra
        Solver-->>Service: Structured optimal or infeasibility result
        Service->>DB: Persist immutable run/plan/scenario (atomic commit)
        DB-->>Service: Committed records
        Service-->>User: HTTP 200 / 201 Structured JSON Response
    end
```

---

## 3. Decoupled LP-to-VRP Allocation & Dispatch Workflow

```mermaid
flowchart LR
    LIVE["Live Operational Tables (Warehouses, Hospitals, Inventory, Demands, Roads)"]
    P3["Phase 3: PuLP CBC Solver (Transportation LP or 4-Stage Lexicographic LP)"]
    RUN["Immutable OptimizationRun + Allocation Records"]
    DEPOT["Per-Depot Grouping by Warehouse Origin"]
    MAT["Directed OSM Distance/Time Matrix (or Synthetic Fallback)"]
    OR["Phase 4–5: Google OR-Tools CVRP (1D Weight Capacity, Split Loads, Multi-Wave)"]
    PLAN["Persisted DispatchPlan -> VehicleAssignment (route_geometry_json) -> DeliveryStop -> ShipmentLine"]
    LIFE["Validated Dispatch Lifecycle (planned -> dispatched -> in_transit -> delivered)"]

    LIVE -->|Read-Only Snapshot| P3
    P3 --> RUN
    RUN -->|Exact Quantity Conservation| DEPOT
    DEPOT --> MAT
    MAT --> OR
    OR --> PLAN
    PLAN --> LIFE
```

---

## 4. Isolated Disaster Scenario Simulation Workflow

```mermaid
flowchart TD
    BASE["Selected Baseline OptimizationRun (Immutable)"]
    SNAP["Read-Only In-Memory Operational Snapshot (Matching Baseline Scope)"]
    DIS["Apply Disruptions: Warehouse Outage, Corridor Closure, OSM way_id Closure, Demand Spike, Vehicle Loss"]
    RELP["Re-Solve LP Allocation (PuLP CBC)"]
    REVRP["Re-Solve Multi-Depot VRP on Isolated OSM Subgraph View"]
    COMP["Compute Baseline vs. Disrupted Deltas (11+ KPIs)"]
    SAVE["Persist Immutable ScenarioRun (Zero Live DB or OSM Cache Mutation)"]

    BASE --> SNAP
    SNAP --> DIS
    DIS --> RELP
    RELP --> REVRP
    REVRP --> COMP
    COMP --> SAVE
```

---

## 5. OpenStreetMap Road-Network Routing & Fallback Workflow

```mermaid
flowchart TD
    REQ["Routing Request (Dispatch Plan / Scenario / Shortest Path)"]
    CHK{"Valid Local OSM Cache Present?"}
    LOAD["Load MultiDiGraph from In-Memory / Disk Cache"]
    SNAP["Snap Active Warehouses & Hospitals to Largest SCC (<= 2.5 km)"]
    FILT["Build Isolated Subgraph View (Exclude closed_way_ids, vehicle_accessible=False, hgv_restricted=True)"]
    DIJK["Single-Source Dijkstra per Facility (min_distance or min_time)"]
    REACH{"Directed Path Exists?"}
    OSMOUT["Return Curved OSM Street Geometry, Distance, Speed-Profile Time & way_ids"]
    UNREACH["Mark Connection Unreachable (Never Substitute Synthetic Leg in OSM Mode)"]
    FALL["Activate Synthetic Corridor Fallback + Emit fallback_warning"]

    REQ --> CHK
    CHK -->|Yes| LOAD
    CHK -->|No / Invalid| FALL
    LOAD --> SNAP
    SNAP --> FILT
    FILT --> DIJK
    DIJK --> REACH
    REACH -->|Yes| OSMOUT
    REACH -->|No| UNREACH
```

---

## 6. Layer Responsibilities & Portability

- **API Routers (`backend/app/api/routes/`)**: Thin HTTP handlers delegating to services; zero embedded solver math.
- **Schemas (`backend/app/schemas/`)**: Strict Pydantic v2 input/output contracts.
- **Optimization & GIS (`backend/app/optimization/`)**: Pure Python Operations Research and NetworkX modules cleanly unit-testable without HTTP or DB coupling.
- **Database Migrations (`backend/app/database/migrations.py`)**: Safe, idempotent additive column migrations preserving historical SQLite data.
- **Configuration**: Environment-driven via `.env` (`DATABASE_URL`, `CORS_ORIGINS`, `GEO_*`, `OSM_*`), portable between SQLite and PostgreSQL.
