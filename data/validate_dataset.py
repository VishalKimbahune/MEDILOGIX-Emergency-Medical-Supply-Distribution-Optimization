"""
Dataset Validation Script for MEDILOGIX.

Validates the six generated synthetic CSV datasets for:
- Required file existence and non-empty tables
- Missing or blank values
- Duplicate primary identifiers
- Foreign key referential integrity
- Non-negative quantities, distances, times, and costs
- Valid geographical coordinates within the configured Pune bounding box
- Supply vs. demand consistency and presence of at least one controlled shortage
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

BASE_DIR: Path = Path(__file__).resolve().parent
SYNTHETIC_DIR: Path = BASE_DIR / "synthetic"

# Configurable Pune urban + Pimpri-Chinchwad bounding box
GEO_MIN_LAT: float = 18.40
GEO_MAX_LAT: float = 18.70
GEO_MIN_LON: float = 73.70
GEO_MAX_LON: float = 74.05

VALID_PRIORITIES: set[str] = {"critical", "high", "normal"}
REQUIRED_FILES: list[str] = [
    "warehouses.csv",
    "hospitals.csv",
    "products.csv",
    "inventory.csv",
    "demands.csv",
    "routes.csv",
]


def load_csv(path: Path) -> list[dict[str, str]]:
    """Read a CSV file into a list of row dicts."""
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_dataset(data_dir: Path = SYNTHETIC_DIR) -> tuple[bool, list[str], dict[str, dict[str, int]]]:
    """
    Run full structural, referential, geographical, and OR-balance checks.

    Returns:
        Tuple of (is_valid, error_messages, supply_demand_summary)
    """
    errors: list[str] = []
    tables: dict[str, list[dict[str, str]]] = {}

    # 1. File presence and missing-value check
    for filename in REQUIRED_FILES:
        file_path = data_dir / filename
        if not file_path.exists():
            errors.append(f"Missing required dataset file: {file_path}")
            continue
        rows = load_csv(file_path)
        if not rows:
            errors.append(f"Dataset file is empty: {filename}")
            continue
        tables[filename] = rows

        for row_num, row in enumerate(rows, start=2):
            for col, val in row.items():
                if val is None or str(val).strip() == "":
                    errors.append(f"{filename} line {row_num}: missing value in column '{col}'")

    if errors:
        return False, errors, {}

    # 2. Primary key uniqueness
    pk_columns = {
        "warehouses.csv": "warehouse_id",
        "hospitals.csv": "hospital_id",
        "products.csv": "product_id",
        "inventory.csv": "inventory_id",
        "demands.csv": "demand_id",
        "routes.csv": "route_id",
    }
    id_sets: dict[str, set[str]] = {}
    for filename, pk_col in pk_columns.items():
        seen: set[str] = set()
        for row_num, row in enumerate(tables[filename], start=2):
            pk_val = row[pk_col].strip()
            if pk_val in seen:
                errors.append(f"{filename} line {row_num}: duplicate identifier '{pk_val}'")
            seen.add(pk_val)
        id_sets[filename] = seen

    warehouse_ids = id_sets["warehouses.csv"]
    hospital_ids = id_sets["hospitals.csv"]
    product_ids = id_sets["products.csv"]

    # 3. Coordinate & attribute validation for warehouses and hospitals
    for filename, id_col in [("warehouses.csv", "warehouse_id"), ("hospitals.csv", "hospital_id")]:
        for row_num, row in enumerate(tables[filename], start=2):
            try:
                lat = float(row["latitude"])
                lon = float(row["longitude"])
            except ValueError:
                errors.append(f"{filename} line {row_num}: non-numeric coordinates for {row[id_col]}")
                continue

            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                errors.append(f"{filename} line {row_num}: invalid WGS84 coordinate ({lat}, {lon})")
            elif not (GEO_MIN_LAT <= lat <= GEO_MAX_LAT and GEO_MIN_LON <= lon <= GEO_MAX_LON):
                errors.append(
                    f"{filename} line {row_num}: coordinate ({lat}, {lon}) outside configured "
                    f"Pune bounds [{GEO_MIN_LAT}-{GEO_MAX_LAT}, {GEO_MIN_LON}-{GEO_MAX_LON}]"
                )

    for row_num, row in enumerate(tables["warehouses.csv"], start=2):
        if int(row["storage_capacity_units"]) <= 0:
            errors.append(f"warehouses.csv line {row_num}: storage_capacity_units must be positive")

    hospital_priority_map: dict[str, str] = {}
    for row_num, row in enumerate(tables["hospitals.csv"], start=2):
        prio = row["priority_level"].strip().lower()
        if prio not in VALID_PRIORITIES:
            errors.append(f"hospitals.csv line {row_num}: invalid priority_level '{prio}'")
        hospital_priority_map[row["hospital_id"]] = prio
        if int(row["bed_capacity"]) <= 0:
            errors.append(f"hospitals.csv line {row_num}: bed_capacity must be positive")

    # 4. Product numeric checks
    for row_num, row in enumerate(tables["products.csv"], start=2):
        if float(row["unit_weight_kg"]) <= 0:
            errors.append(f"products.csv line {row_num}: unit_weight_kg must be positive")
        if float(row["base_transport_cost_per_km"]) < 0:
            errors.append(f"products.csv line {row_num}: base_transport_cost_per_km cannot be negative")

    # 5. Inventory FK, duplicates, and non-negativity
    supply_by_product: dict[str, int] = defaultdict(int)
    warehouse_total_stock: dict[str, int] = defaultdict(int)
    seen_inv_pairs: set[tuple[str, str]] = set()
    for row_num, row in enumerate(tables["inventory.csv"], start=2):
        wh_id = row["warehouse_id"]
        prod_id = row["product_id"]
        if wh_id not in warehouse_ids:
            errors.append(f"inventory.csv line {row_num}: invalid warehouse_id '{wh_id}'")
        if prod_id not in product_ids:
            errors.append(f"inventory.csv line {row_num}: invalid product_id '{prod_id}'")
        pair = (wh_id, prod_id)
        if pair in seen_inv_pairs:
            errors.append(f"inventory.csv line {row_num}: duplicate (warehouse_id, product_id) pair {pair}")
        seen_inv_pairs.add(pair)

        qty_avail = int(row["quantity_available"])
        qty_res = int(row["quantity_reserved"])
        reorder = int(row["reorder_level"])
        if qty_avail < 0 or qty_res < 0 or reorder < 0:
            errors.append(f"inventory.csv line {row_num}: negative inventory quantity detected")
        if qty_res > qty_avail:
            errors.append(f"inventory.csv line {row_num}: quantity_reserved exceeds quantity_available")

        supply_by_product[prod_id] += qty_avail - qty_res
        warehouse_total_stock[wh_id] += qty_avail

    # Check warehouse capacity consistency
    for row in tables["warehouses.csv"]:
        wh_id = row["warehouse_id"]
        capacity = int(row["storage_capacity_units"])
        if warehouse_total_stock[wh_id] > capacity:
            errors.append(
                f"Warehouse {wh_id}: total inventory ({warehouse_total_stock[wh_id]}) "
                f"exceeds storage_capacity_units ({capacity})"
            )

    # 6. Demand FK, priority consistency, and non-negativity
    demand_by_product: dict[str, int] = defaultdict(int)
    seen_dem_pairs: set[tuple[str, str]] = set()
    for row_num, row in enumerate(tables["demands.csv"], start=2):
        hosp_id = row["hospital_id"]
        prod_id = row["product_id"]
        if hosp_id not in hospital_ids:
            errors.append(f"demands.csv line {row_num}: invalid hospital_id '{hosp_id}'")
        if prod_id not in product_ids:
            errors.append(f"demands.csv line {row_num}: invalid product_id '{prod_id}'")
        pair = (hosp_id, prod_id)
        if pair in seen_dem_pairs:
            errors.append(f"demands.csv line {row_num}: duplicate (hospital_id, product_id) pair {pair}")
        seen_dem_pairs.add(pair)

        qty_req = int(row["quantity_requested"])
        if qty_req < 0:
            errors.append(f"demands.csv line {row_num}: negative quantity_requested detected")

        prio = row["priority_level"].strip().lower()
        if prio not in VALID_PRIORITIES:
            errors.append(f"demands.csv line {row_num}: invalid priority_level '{prio}'")
        elif hosp_id in hospital_priority_map and hospital_priority_map[hosp_id] != prio:
            errors.append(
                f"demands.csv line {row_num}: priority '{prio}' mismatches hospital "
                f"{hosp_id} priority '{hospital_priority_map[hosp_id]}'"
            )

        demand_by_product[prod_id] += qty_req

    # 7. Route FK, completeness, and non-negativity
    seen_route_pairs: set[tuple[str, str]] = set()
    for row_num, row in enumerate(tables["routes.csv"], start=2):
        wh_id = row["warehouse_id"]
        hosp_id = row["hospital_id"]
        if wh_id not in warehouse_ids:
            errors.append(f"routes.csv line {row_num}: invalid warehouse_id '{wh_id}'")
        if hosp_id not in hospital_ids:
            errors.append(f"routes.csv line {row_num}: invalid hospital_id '{hosp_id}'")
        pair = (wh_id, hosp_id)
        if pair in seen_route_pairs:
            errors.append(f"routes.csv line {row_num}: duplicate route pair {pair}")
        seen_route_pairs.add(pair)

        if float(row["distance_km"]) <= 0:
            errors.append(f"routes.csv line {row_num}: distance_km must be positive")
        if float(row["estimated_travel_time_min"]) <= 0:
            errors.append(f"routes.csv line {row_num}: estimated_travel_time_min must be positive")
        if float(row["base_transport_cost_per_unit"]) < 0:
            errors.append(f"routes.csv line {row_num}: base_transport_cost_per_unit cannot be negative")

    # 8. Supply vs. demand balance check (ensure at least one controlled shortage)
    balance_summary: dict[str, dict[str, int]] = {}
    shortage_products: list[str] = []
    for prod_id in sorted(product_ids):
        supply = supply_by_product[prod_id]
        demand = demand_by_product[prod_id]
        gap = supply - demand
        balance_summary[prod_id] = {"supply": supply, "demand": demand, "net_balance": gap}
        if gap < 0:
            shortage_products.append(prod_id)

    if not shortage_products:
        errors.append(
            "Dataset lacks a controlled supply shortage; expected at least one product "
            "where aggregate demand exceeds aggregate warehouse supply."
        )

    return len(errors) == 0, errors, balance_summary


def main() -> None:
    is_valid, errors, summary = validate_dataset()
    print("MEDILOGIX Dataset Validation Report")
    print("=" * 40)
    for prod_id, stats in summary.items():
        status = "CONTROLLED SHORTAGE" if stats["net_balance"] < 0 else "ADEQUATE"
        print(
            f"  {prod_id}: supply={stats['supply']}, demand={stats['demand']}, "
            f"net={stats['net_balance']:+d} [{status}]"
        )

    if is_valid:
        print("\nRESULT: PASS — All validation checks succeeded.")
        sys.exit(0)
    else:
        print(f"\nRESULT: FAIL — {len(errors)} issue(s) found:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
