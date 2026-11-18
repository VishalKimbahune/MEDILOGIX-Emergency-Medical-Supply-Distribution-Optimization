# MEDILOGIX — API Documentation

Base URL (local development): `http://127.0.0.1:8000`  
Interactive OpenAPI / Swagger UI: `http://127.0.0.1:8000/docs`

---

## 1. System Health

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/health` | Returns backend service status, application metadata, configured geographical region, and database connectivity status. |

## 2. Core Resource Endpoints

| Module | Base Path | Supported Methods (Initial Skeleton & CRUD) |
| :--- | :--- | :--- |
| Warehouses | `/api/warehouses` | `GET /`, `GET /{warehouse_id}`, `POST /`, `PUT /{warehouse_id}`, `DELETE /{warehouse_id}` |
| Hospitals | `/api/hospitals` | `GET /`, `GET /{hospital_id}`, `POST /`, `PUT /{hospital_id}`, `DELETE /{hospital_id}` |
| Products | `/api/products` | `GET /`, `GET /{product_id}`, `POST /`, `PUT /{product_id}`, `DELETE /{product_id}` |
| Inventory | `/api/inventory` | `GET /`, `GET /{inventory_id}`, `POST /`, `PUT /{inventory_id}`, `DELETE /{inventory_id}` |
| Demands | `/api/demands` | `GET /`, `GET /{demand_id}`, `POST /`, `PUT /{demand_id}`, `DELETE /{demand_id}` |

## 3. Operations Research, Routing, Scenarios & Analytics Endpoints

| Module | Endpoint | Method | Description |
| :--- | :--- | :--- | :--- |
| Optimization | `/api/optimization/runs` | `GET` | List recorded optimization runs. |
| Optimization | `/api/optimization/transportation` | `POST` | Run multi-commodity transportation LP (PuLP). |
| Optimization | `/api/optimization/priority` | `POST` | Run lexicographic priority shortage optimization (PuLP). |
| Routes | `/api/routes` | `GET` | List warehouse-hospital route corridors. |
| Routes | `/api/routes/shortest-path` | `POST` | Compute shortest path via NetworkX Dijkstra. |
| Routes | `/api/routes/vrp` | `POST` | Execute OR-Tools Vehicle Routing Problem extension (TODO). |
| Scenarios | `/api/scenarios` | `GET`, `POST` | List or create disaster simulation scenarios. |
| Scenarios | `/api/scenarios/{scenario_id}/simulate` | `POST` | Execute scenario perturbation and re-optimize (TODO). |
| Analytics | `/api/analytics/summary` | `GET` | Aggregate live database KPIs (warehouses, hospitals, stock, open demand, critical alerts). |
| Analytics | `/api/analytics/supply-demand-gap` | `GET` | Product-wise supply vs. demand comparison. |
