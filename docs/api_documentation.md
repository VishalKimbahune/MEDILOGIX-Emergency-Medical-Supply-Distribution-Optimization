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

## 4. Routing, Scenarios & Analytics Endpoints

| Module | Endpoint | Method | Description |
| :--- | :--- | :--- | :--- |
| Routes | `/api/routes` | `GET` | List warehouse-hospital route corridors. |
| Routes | `/api/routes/shortest-path` | `POST` | Compute shortest path via NetworkX Dijkstra. |
| Routes | `/api/routes/vrp` | `POST` | Google OR-Tools Capacitated VRP extension (Phase 4 TODO). |
| Scenarios | `/api/scenarios` | `GET`, `POST`, `DELETE /{id}` | Manage disaster simulation scenarios. |
| Scenarios | `/api/scenarios/{scenario_id}/simulate` | `POST` | Execute scenario perturbation and re-optimize (Planned). |
| Analytics | `/api/analytics/summary` | `GET` | Aggregate live database KPIs and latest optimization run cost/fulfillment. |
| Analytics | `/api/analytics/supply-demand-gap` | `GET` | Product-wise supply vs. demand comparison. |
