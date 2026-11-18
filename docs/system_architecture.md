# MEDILOGIX — System Architecture

## 1. High-Level Architecture

MEDILOGIX follows a clean, decoupled three-tier architecture with a dedicated Operations Research & Simulation engine layer:

```text
+-------------------------------------------------------------------+
|                    React + Vite Frontend (SPA)                    |
|   Tailwind CSS | React Router | Axios | Recharts | React Leaflet  |
+---------------------------------+---------------------------------+
                                  | REST / JSON (CORS enabled)
+---------------------------------v---------------------------------+
|                    FastAPI Application Layer                      |
|   API Routers (/api/*)  -->  Pydantic v2 Request/Response Schemas |
+---------------------------------+---------------------------------+
                                  |
         +------------------------+------------------------+
         |                                                 |
+--------v-------------------------+   +-------------------v--------------------+
|     Domain Services Layer        |   |   Operations Research & Simulation     |
|  Warehouse / Hospital /          |   |   - transportation.py (PuLP LP)        |
|  Inventory / Demand Services     |   |   - priority.py (Lexicographic LP)     |
+--------+-------------------------+   |   - linear_programming.py (Builders)   |
         |                             |   - shortest_path.py (NetworkX)        |
         |                             |   - vehicle_routing.py (OR-Tools VRP)  |
         |                             |   - scenario_engine.py (Disruptions)   |
         +------------------------+----+-------------------+--------------------+
                                  |
+---------------------------------v---------------------------------+
|            Persistence Layer (SQLAlchemy 2.0 ORM)                 |
|        PostgreSQL (Production)  |  SQLite (Local Dev)             |
+-------------------------------------------------------------------+
```

## 2. Separation of Concerns

- **API Routes (`backend/app/api/routes/`)**: HTTP routing, request parsing, status codes, and dependency injection only. No optimization math or raw SQL.
- **Schemas (`backend/app/schemas/`)**: Strict Pydantic v2 validation and response serialization.
- **Services (`backend/app/services/`)**: Business rules, CRUD orchestration, and transaction boundaries.
- **Optimization (`backend/app/optimization/`)**: Pure Operations Research formulations decoupled from FastAPI and HTTP transport. Allocation optimization (`transportation.py`, `priority.py`) is strictly separated from vehicle routing (`shortest_path.py`, `vehicle_routing.py`).
- **Simulation (`backend/app/simulation/`)**: Perturbs network state (disabled warehouses, closed roads, demand multipliers) and delegates solving back to the OR modules.
- **Frontend (`frontend/src/`)**: Modular pages, shared layout (`MainLayout.jsx`), service modules (`services/*.js`), and reusable UI/map/chart components. Live API status and placeholder views are visually distinguished.

## 3. Configuration & Portability

- Both frontend and backend load runtime configuration from environment variables (`.env`), with `.env.example` templates committed for reproducibility.
- `DATABASE_URL` seamlessly toggles between SQLite for rapid local prototyping and PostgreSQL (`psycopg2-binary`) for production/academic server deployments.
