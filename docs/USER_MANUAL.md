# MEDILOGIX — Beginner-Friendly User Manual

This manual explains how to install, configure, run, and operate **MEDILOGIX** on a Windows machine from scratch.

---

## 1. Prerequisites

- **Python 3.11+** installed and available in PowerShell (`python --version`)
- **Node.js 18+** and **npm** (`node --version`, `npm --version`)
- **Git** (optional, for cloning the repository)

---

## 2. Installation & Environment Setup

### Step 1: Clone or Open the Repository

```powershell
cd "d:\MEDILOGIX- Optimize Medical Supply Distribution"
```

### Step 2: Configure Environment Files

Copy the safe example templates (never commit `.env` files to Git):

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

Default settings work out of the box with local SQLite (`backend/medilogix_dev.db`), Pune & Pimpri-Chinchwad coordinates (`18.40–18.70, 73.70–74.05`), and backend API `http://127.0.0.1:8000/api`.

### Step 3: Set Up Backend Python Virtual Environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Step 4: Initialize & Seed the Database (First Time Only)

```powershell
# From backend/
python -m app.database.init_db
```

This creates all 16 tables non-destructively and seeds the reproducible Pune & Pimpri-Chinchwad synthetic dataset (`RANDOM_SEED = 42`).

### Step 5: Optional One-Time OpenStreetMap Road Network Cache

```powershell
# From repository root:
backend\.venv\Scripts\python.exe data\fetch_osm_network.py
```

Downloads Pune/PCMC arterial/collector roads once into `data/processed/pune_osm_road_graph.json`. If skipped or offline, MEDILOGIX automatically uses the **Synthetic Corridor Fallback**.

### Step 6: Install Frontend Packages

```powershell
cd frontend
npm install
```

---

## 3. Starting the Application

Open **two PowerShell terminals**:

- **Terminal 1 (FastAPI Backend)**:
  ```powershell
  cd backend
  .\.venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8000
  ```
  Verify: open `http://127.0.0.1:8000/api/health` or Swagger UI at `http://127.0.0.1:8000/docs`.

- **Terminal 2 (React Frontend)**:
  ```powershell
  cd frontend
  npm run dev
  ```
  Open `http://localhost:5173` in your browser. The top-right status pill should turn green (**API Connected**).

---

## 4. Step-by-Step Operational Workflows

### 4.1 Dashboard
- Displays live operational KPIs (**Total Warehouses**, **Total Hospitals**, **Available Inventory**, **Current Open Demand**, **Critical Hospital Alerts**, **Inventory Utilization**) alongside the latest historical solver run snapshot (**Fulfillment** & **Distribution Cost**), interactive Pune network map, and recent runs.

### 4.2 Adding & Managing Warehouses
1. Navigate to **Warehouses** in the left sidebar.
2. Click **Add Warehouse**, enter a unique code (e.g., `WH-04`), name, Pune locality, coordinates, and storage capacity, then click **Save**.
3. Use search, sort, Edit, View, or Delete (protected by foreign-key checks so referenced warehouses cannot be accidentally removed).

### 4.3 Adding & Escalating Hospitals
1. Navigate to **Hospitals**.
2. Click **Register Hospital**, enter code, name, area, coordinates, bed capacity, and priority tier (`critical`, `high`, or `normal`).
3. To escalate a hospital during an emergency, edit its priority tier to `critical` so Tier-1 lexicographic optimization prioritizes it first.

### 4.4 Managing Inventory
1. Navigate to **Inventory**.
2. Switch between **Grouped by Warehouse** and **Tabular** views.
3. Adjust stock levels or add new warehouse-product stock records; low-stock items below reorder thresholds are highlighted automatically.

### 4.5 Creating & Updating Hospital Demand Requests
1. Navigate to **Demand Requests**.
2. Filter by priority, status (`open`, `partially_fulfilled`, `fulfilled`), or hospital.
3. Click **New Demand Request** to log emergency medical supply requirements.

### 4.6 Running & Comparing LP Optimization Models
1. Navigate to **Optimization**.
2. Optionally select specific warehouses, hospitals, or products (leave all selected for network-wide optimization).
3. Click:
   - **Run Transportation LP** — minimizes total shortage and transport cost (priority-neutral).
   - **Run Lexicographic Priority LP** — protects **Critical → High → Normal** hospitals sequentially before minimizing cost.
   - **Compare Both Models** — solves both models side-by-side and quantifies the exact cost vs. critical-care fulfillment trade-off.
4. Inspect historical runs anytime under the **Run History** tab without re-running the solver.

### 4.7 Generating Dispatch Routes & Tracking Deliveries
1. Navigate to **Delivery Routes**.
2. Select a completed **Optimization Run** (Phase 3 LP allocations).
3. Choose the **Routing Objective**:
   - **Minimum Road Distance (km)** *(default)*
   - **Minimum Estimated Travel Time (min)**
4. Optionally enter comma-separated **Closed OSM Way IDs** to test street closures.
5. Click **Generate Vehicle Routes** to run Google OR-Tools Multi-Depot CVRP on the cached Pune OSM road network (or synthetic fallback).
6. Inspect:
   - **Vehicle Assignments & Stops** tab: payload utilization, ordered stops, and product shipment lines (100% conserved from LP).
   - **Route Map View** tab: curved OSM street polylines, numbered stops, closed roads, and interactive layer/vehicle/priority filters.
7. Progress the dispatch lifecycle using the header buttons (**Dispatch Fleet → Mark In Transit → Mark All Delivered**) or update individual hospital stop statuses (`planned` → `dispatched` → `delivered`).

### 4.8 Synchronizing OpenStreetMap & Exploring Shortest Paths
1. On **Delivery Routes**, open the **Road Network & Corridors** tab.
2. Inspect cached OSM node count, directed edge count, main SCC connectivity, facility snapping distances, and `© OpenStreetMap contributors (ODbL 1.0)` attribution.
3. Click **Synchronize OSM Network** to verify/reuse the local cache (or check **Force Overpass re-download** to refresh from Overpass). If Overpass is unreachable, MEDILOGIX continues safely using the existing cache or synthetic fallback.
4. Use the **Directed OSM Shortest-Path Explorer** below it to test directed routes between any two facilities with optional closed `way_id` exclusions.

### 4.9 Simulating Disaster Disruptions
1. Navigate to **Scenario Simulator**.
2. Pick a **Baseline Optimization Run** and choose a disruption type:
   - **Warehouse Outage**, **Road Corridor / OSM Way Closure**, **Hospital Demand Spike (+%)**, **Vehicle Unavailability**, or **Combined Multi-Factor Disruption**.
3. Click **Run Disaster Simulation**.
4. Review baseline vs. disrupted KPI deltas (demand, allocation, unmet demand, Critical/High/Normal fulfillment, cost, distance, duration, vehicles, routes) and open **Disruption & Route Map** to see rerouted paths and closed roads.
5. Note: simulations run strictly in memory and **never modify live inventory, demands, roads, vehicles, or baseline runs**.

### 4.10 Reading Analytics & Reports
1. Navigate to **Analytics & Reports**.
2. Switch across the 4 tabs:
   - **Supply Chain (Live)** — current operational inventory, demand, and supply-demand gap.
   - **Optimization (Snapshot)** — latest historical LP run performance, priority fulfillment, hospital coverage, and multi-run cost comparison.
   - **Dispatch & Fleet** — vehicle payload utilization, distance/duration totals, and delivery stop completion breakdown.
   - **Disaster Scenarios** — simulation count, average impact by disruption type, and baseline vs. disrupted comparison.


---

## 5. Authentication & Four Role-Based Portals

MEDILOGIX enforces strict backend Role-Based Access Control (RBAC) across four separate portals:

### 5.1 Initial Sign-In & Registration
1. Provision an initial Administrator via CLI (`python backend\scripts\create_admin.py --email admin@medilogix.org`).
2. Public users register at `/register` as **Hospital**, **Warehouse**, or **Delivery** (never Admin) and select their associated hospital or warehouse.
3. New registrations start as **Pending Approval** until an Administrator approves them at `/admin/users`.

### 5.2 Admin Portal (`/admin/*`)
- Full access to Command Overview, Pending User Approvals (`/admin/users`), Pending Hospital Order Approvals (`/admin/demands`), Fleet Vehicle & Driver Assignment (`/admin/vehicles`), Optimization Engine, OR-Tools OSM Dispatch, Disaster Simulator, Analytics, and Append-Only Audit Logs (`/admin/audit-logs`).

### 5.3 Hospital Portal (`/hospital/*`)
- Scoped strictly to the logged-in user's assigned hospital.
- Submit single- or multi-product emergency supply orders at `/hospital/orders/new` (enters `pending_approval`).
- Track every order live via the 6-stage visual timeline (`Submitted -> Approved -> Allocated -> Dispatched -> In Transit -> Delivered`) at `/hospital/orders`.

### 5.4 Warehouse Portal (`/warehouse/*`)
- Scoped strictly to the logged-in user's assigned warehouse.
- Record controlled stock-in and adjustments with mandatory audit reasons (`StockMovement` history) at `/warehouse/inventory`.
- Manage outgoing dispatch preparation (`Pending -> Preparing -> Ready for Dispatch -> Handed Over`) at `/warehouse/shipments`.
- Toggle warehouse operational status (`ACTIVE` / `INACTIVE` / `MAINTENANCE`) at `/warehouse/profile`.

### 5.5 Delivery Portal (`/delivery/*`)
- Scoped strictly to the logged-in driver's assigned vehicles & dispatch routes.
- Inspect assigned curved Pune OpenStreetMap routes on the interactive map at `/delivery/assignments`.
- Progress stop status (`Dispatched -> In Transit`) and submit full or partial delivery confirmations (capped at planned quantities, protected against duplicate confirmations).
