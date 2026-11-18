# MEDILOGIX

**Emergency Medical Supply Distribution Optimization Using Operations Research and Intelligent Decision Support**

MEDILOGIX is a modular, full-stack decision-support platform built for B.Tech final-year / Project-Based Learning (PBL) work in **Operations Research (OR)** and **Data Science / Supply Chain Management (DSCM)**. It models and optimizes emergency medical supply allocation from multiple distribution warehouses to hospitals across **Pune urban area and Pimpri-Chinchwad, Maharashtra** (with configurable geographical boundaries for expansion to the full Pune district).

> **Data Disclaimer**: All warehouse facilities are explicitly modeled as *fictional simulation hubs*, and all hospital demand, inventory levels, and travel times are *synthetic and illustrative*. Geographical coordinates correspond to general Pune and Pimpri-Chinchwad localities (aligned with OpenStreetMap). Simulated travel times do **not** represent live or real-time traffic.

---

## Key Capabilities & Development Progress

- **Phase 1 (Complete)**: Modular FastAPI + SQLAlchemy backend, reproducible synthetic Pune & Pimpri-Chinchwad dataset generator & validator (`RANDOM_SEED = 42`), React + Vite + Tailwind CSS enterprise shell, interactive OpenStreetMap network map, and documentation.
- **Phase 2 (Complete)**: Full end-to-end CRUD management modules for **Warehouses**, **Hospitals** (including live emergency priority escalation), **Inventory** (grouped & tabular views, low-stock alerts, stock adjustment confirmation), and **Hospital Demand Requests**, with strict foreign-key protection.
- **Phase 3 (Complete)**: Full **Operations Research Optimization Engine** (`PuLP CBC`):
  - **Multi-Commodity Transportation LP** (`POST /api/optimization/transportation`)
  - **Sequential 4-Stage Lexicographic Priority Shortage Optimization** (`POST /api/optimization/priority`: Critical → High → Normal → Transport Cost)
  - **Side-by-Side Model Comparison** (`POST /api/optimization/compare`) showing exact cost vs. priority-fulfillment trade-offs
  - **Immutable Run History Inspection** (`GET /api/optimization/runs` & `GET /api/optimization/runs/{id}`)
  - **Interactive Optimization Workbench** with scope selection, priority-tier analysis, sortable/filterable allocations with corridor metadata, 5 Recharts visualizations, and an Academic Mathematical Formulation panel
- **Upcoming Phases**: Google OR-Tools Capacitated Vehicle Routing (CVRP), Overpass API road-network ingestion, and interactive Disaster Scenario Simulator comparisons.

### Verified Baseline OR Results (`seed=42` Synthetic Dataset)

| Model | Transport Cost (INR) | Critical Fulfillment | High Fulfillment | Normal Fulfillment |
| :--- | :---: | :---: | :---: | :---: |
| **Transportation Cost LP** | ₹134,932.40 | 91.68% (76 unmet) | 89.32% (108 unmet) | 99.27% (5 unmet) |
| **4-Stage Lexicographic Priority LP** | ₹144,463.31 | **100.00% (0 unmet)** | **98.71% (13 unmet)** | 74.38% (176 unmet) |

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
