# MEDILOGIX

**Emergency Medical Supply Distribution Optimization Using Operations Research and Intelligent Decision Support**

MEDILOGIX is a modular, full-stack decision-support platform built for B.Tech final-year / Project-Based Learning (PBL) work in **Operations Research (OR)** and **Data Science / Supply Chain Management (DSCM)**. It models and optimizes emergency medical supply allocation from multiple distribution warehouses to hospitals across **Pune urban area and Pimpri-Chinchwad, Maharashtra** (with configurable geographical boundaries for expansion to the full Pune district).

> **Data Disclaimer**: All warehouse facilities are explicitly modeled as *fictional simulation hubs*, and all hospital demand, inventory levels, and travel times are *synthetic and illustrative*. Geographical coordinates correspond to general Pune and Pimpri-Chinchwad localities (aligned with OpenStreetMap). Simulated travel times do **not** represent live or real-time traffic.

---

## Key Capabilities & Planned Modules

1. **Emergency Command Dashboard** — Real-time overview of network capacity, open demand, critical alerts, map visualization, and optimization runs.
2. **Warehouse Management** — Manage simulation hubs, capacities, and operational status.
3. **Hospital Management** — Track hospitals, localities, and emergency priority levels (`critical`, `high`, `normal`).
4. **Medical Product Management** — Manage essential supplies (Oxygen Cylinders, IV Fluid Cartons, Trauma Kits, Essential Medicine Boxes).
5. **Inventory Management** — Track warehouse-level stock per medical product.
6. **Hospital Demand Management** — Capture and prioritize hospital supply requests.
7. **Transportation Optimization** — Multi-commodity Linear Programming (PuLP) to minimize distribution cost.
8. **Emergency Priority Management** — Lexicographic shortage optimization prioritizing critical hospitals before high and normal tiers.
9. **Delivery Route Optimization** — Shortest-path computation (NetworkX / Dijkstra) and Vehicle Routing Problem (Google OR-Tools) extensions.
10. **Disaster Scenario Simulator** — Evaluate warehouse outages, road closures, and demand surges.
11. **Optimization History** — Persist runs, allocations, and solver diagnostics.
12. **Performance Analytics & Reports** — Fulfillment rates, cost metrics, and unmet demand breakdowns.

---

## Technology Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend** | React (Vite), JavaScript, Tailwind CSS, React Router, Axios, Lucide React, Recharts, React Leaflet |
| **Backend** | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0 |
| **Operations Research** | PuLP (LP / Transportation / Lexicographic Priority), Google OR-Tools (VRP), NetworkX (Shortest Path), NumPy, Pandas |
| **Database** | PostgreSQL (production target), SQLite (local development fallback) |
| **Testing** | Pytest, HTTPX |
| **GIS / Mapping** | OpenStreetMap tiles, Overpass API (planned), NetworkX |

---

## Repository Structure

```text
MEDILOGIX/
├── frontend/          # React + Vite + Tailwind CSS enterprise dashboard
├── backend/           # FastAPI API, SQLAlchemy models, OR optimization modules, tests
├── data/              # Reproducible synthetic dataset generator, validator, CSVs
├── notebooks/         # Exploratory data, demand, and optimization Jupyter notebooks
├── docs/              # Architecture, mathematical formulation, DB & API documentation
├── .env.example       # Root environment configuration template
├── .gitignore
└── README.md
```

---

## Quick Start

### 1. Generate & Validate Synthetic Dataset

```bash
python data/generate_dataset.py
python data/validate_dataset.py
```

### 2. Backend Setup (FastAPI + SQLAlchemy + OR Stack)

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python -m app.database.init_db
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify health endpoint:
- Health Check: `GET http://127.0.0.1:8000/api/health`
- Interactive API Docs (Swagger): `http://127.0.0.1:8000/docs`

### 3. Frontend Setup (React + Vite + Tailwind CSS)

```bash
cd frontend
copy .env.example .env
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### 4. Run Automated Tests

```bash
cd backend
pytest -v
```

---

## Documentation

- [Project Overview](docs/project_overview.md)
- [System Architecture](docs/system_architecture.md)
- [Mathematical Model](docs/mathematical_model.md)
- [Database Design](docs/database_design.md)
- [Dataset Documentation](docs/dataset_documentation.md)
- [API Documentation](docs/api_documentation.md)
