# MEDILOGIX — Database Design

## 1. Persistence Strategy

- **ORM**: SQLAlchemy 2.0 declarative models (`backend/app/models/`).
- **Target Production Database**: PostgreSQL (`postgresql+psycopg2://...`).
- **Local Development Fallback**: SQLite (`sqlite:///./medilogix_dev.db`) enabled seamlessly via `DATABASE_URL`.
- **Conventions**: Surrogate integer primary keys (`id`) combined with unique domain codes (e.g., `WH-01`, `HOSP-01`, `PROD-01`), indexed foreign keys, and UTC `created_at` / `updated_at` timestamps.

## 2. Core Entities & Relationships

| Table | Model | Key Columns & Foreign Keys |
| :--- | :--- | :--- |
| `warehouses` | `Warehouse` | `id` (PK), `code` (unique, indexed), `name`, `area`, `city`, `latitude`, `longitude`, `storage_capacity_units`, `status`, `is_synthetic_hub` |
| `hospitals` | `Hospital` | `id` (PK), `code` (unique, indexed), `name`, `area`, `city`, `latitude`, `longitude`, `priority_level`, `bed_capacity`, `status`, `is_synthetic_profile` |
| `products` | `Product` | `id` (PK), `code` (unique, indexed), `name`, `category`, `unit`, `unit_weight_kg`, `base_transport_cost_per_km`, `cold_chain_required` |
| `inventory` | `Inventory` | `id` (PK), `inventory_code` (unique), `warehouse_id` (FK -> `warehouses.id`), `product_id` (FK -> `products.id`), `quantity_available`, `quantity_reserved`, `reorder_level`; unique `(warehouse_id, product_id)` |
| `demands` | `Demand` | `id` (PK), `demand_code` (unique), `hospital_id` (FK -> `hospitals.id`), `product_id` (FK -> `products.id`), `quantity_requested`, `priority_level`, `status` |
| `roads` | `Road` | `id` (PK), `route_code` (unique), `warehouse_id` (FK -> `warehouses.id`), `hospital_id` (FK -> `hospitals.id`), `distance_km`, `estimated_travel_time_min`, `base_transport_cost_per_unit`, `is_available`, `road_condition` |
| `vehicles` | `Vehicle` | `id` (PK), `vehicle_code` (unique), `warehouse_id` (FK -> `warehouses.id`), `vehicle_type`, `capacity_kg`, `status` |
| `scenarios` | `Scenario` | `id` (PK), `name`, `description`, `scenario_type`, `parameters_json`, `is_active` |
| `optimization_runs` | `OptimizationRun` | `id` (PK), `run_code` (unique), `model_type`, `scenario_id` (nullable FK -> `scenarios.id`), `solver_status`, `total_cost`, `total_allocated`, `total_unmet_demand`, `execution_time_ms`, `summary_json` |
| `allocations` | `Allocation` | `id` (PK), `optimization_run_id` (FK -> `optimization_runs.id`), `warehouse_id` (FK), `hospital_id` (FK), `product_id` (FK), `quantity_allocated`, `unmet_quantity`, `transport_cost` |
| `deliveries` | `Delivery` | `id` (PK), `optimization_run_id` (FK -> `optimization_runs.id`), `vehicle_id` (nullable FK -> `vehicles.id`), `warehouse_id` (FK), `hospital_id` (FK), `route_distance_km`, `estimated_duration_min`, `status`, `route_sequence_json` |

## 3. Initialization & Seeding

Run the database initializer from `backend/`:

```bash
python -m app.database.init_db
```

This creates all tables via `Base.metadata.create_all(bind=engine)` and seeds the database idempotently from `data/synthetic/*.csv` using `app/utils/dataset_loader.py`.
