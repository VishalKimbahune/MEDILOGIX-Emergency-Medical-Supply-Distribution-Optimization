"""
Reproducible Synthetic Dataset Generator for MEDILOGIX.

Generates synthetic operational datasets for emergency medical supply
distribution across Pune urban area and Pimpri-Chinchwad, Maharashtra.

IMPORTANT DISCLAIMER:
- Warehouse facilities are explicitly fictional simulation hubs.
- Hospital names represent synthetic simulation profiles anchored to
  general Pune / Pimpri-Chinchwad locality coordinates.
- All inventory, demand, cost, and travel-time figures are illustrative
  synthetic values and do NOT represent real hospital operations or
  live traffic conditions.
"""

from __future__ import annotations

import csv
import math
import random
from pathlib import Path
from typing import Any

# Fixed seed for deterministic reproducibility
RANDOM_SEED: int = 42

# Configurable geographical boundary (Pune Urban & Pimpri-Chinchwad default;
# expandable to the wider Pune district via configuration).
GEO_BOUNDS: dict[str, float] = {
    "min_lat": 18.40,
    "max_lat": 18.70,
    "min_lon": 73.70,
    "max_lon": 74.05,
}

# Average synthetic urban road tortuosity & speed assumptions
ROAD_TORTUOSITY_FACTOR: float = 1.28
AVG_URBAN_SPEED_KMPH: float = 28.0

BASE_DIR: Path = Path(__file__).resolve().parent
OUTPUT_DIR: Path = BASE_DIR / "synthetic"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance in kilometers between two WGS84 points."""
    earth_radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return earth_radius_km * c


def build_warehouses() -> list[dict[str, Any]]:
    """Define 3 fictional medical logistics simulation hubs in Pune & PCMC."""
    return [
        {
            "warehouse_id": "WH-01",
            "name": "Pimpri Regional Medical Hub (Fictional Simulation Hub)",
            "area": "Pimpri",
            "city": "Pimpri-Chinchwad",
            "latitude": 18.6298,
            "longitude": 73.7997,
            "storage_capacity_units": 5000,
            "status": "active",
            "is_synthetic_hub": True,
        },
        {
            "warehouse_id": "WH-02",
            "name": "Swargate Central Emergency Depot (Fictional Simulation Hub)",
            "area": "Swargate",
            "city": "Pune",
            "latitude": 18.5018,
            "longitude": 73.8636,
            "storage_capacity_units": 4500,
            "status": "active",
            "is_synthetic_hub": True,
        },
        {
            "warehouse_id": "WH-03",
            "name": "Wagholi Eastern Logistics Hub (Fictional Simulation Hub)",
            "area": "Wagholi",
            "city": "Pune",
            "latitude": 18.5808,
            "longitude": 73.9787,
            "storage_capacity_units": 4000,
            "status": "active",
            "is_synthetic_hub": True,
        },
    ]


def build_hospitals() -> list[dict[str, Any]]:
    """Define 8 synthetic hospital profiles across Pune & Pimpri-Chinchwad."""
    return [
        {
            "hospital_id": "HOSP-01",
            "name": "Shivajinagar Civic Trauma Center (Synthetic Profile)",
            "area": "Shivajinagar",
            "city": "Pune",
            "latitude": 18.5308,
            "longitude": 73.8475,
            "priority_level": "critical",
            "bed_capacity": 420,
            "status": "active",
            "is_synthetic_profile": True,
        },
        {
            "hospital_id": "HOSP-02",
            "name": "Aundh District Care Hospital (Synthetic Profile)",
            "area": "Aundh",
            "city": "Pune",
            "latitude": 18.5590,
            "longitude": 73.8077,
            "priority_level": "high",
            "bed_capacity": 280,
            "status": "active",
            "is_synthetic_profile": True,
        },
        {
            "hospital_id": "HOSP-03",
            "name": "Baner Emergency Medical Unit (Synthetic Profile)",
            "area": "Baner",
            "city": "Pune",
            "latitude": 18.5590,
            "longitude": 73.7868,
            "priority_level": "normal",
            "bed_capacity": 180,
            "status": "active",
            "is_synthetic_profile": True,
        },
        {
            "hospital_id": "HOSP-04",
            "name": "Kothrud Multi-Specialty Clinic (Synthetic Profile)",
            "area": "Kothrud",
            "city": "Pune",
            "latitude": 18.5074,
            "longitude": 73.8077,
            "priority_level": "high",
            "bed_capacity": 250,
            "status": "active",
            "is_synthetic_profile": True,
        },
        {
            "hospital_id": "HOSP-05",
            "name": "Kondhwa Community Health Center (Synthetic Profile)",
            "area": "Kondhwa",
            "city": "Pune",
            "latitude": 18.4695,
            "longitude": 73.8890,
            "priority_level": "critical",
            "bed_capacity": 310,
            "status": "active",
            "is_synthetic_profile": True,
        },
        {
            "hospital_id": "HOSP-06",
            "name": "Hadapsar Industrial Area Hospital (Synthetic Profile)",
            "area": "Hadapsar",
            "city": "Pune",
            "latitude": 18.5089,
            "longitude": 73.9260,
            "priority_level": "high",
            "bed_capacity": 260,
            "status": "active",
            "is_synthetic_profile": True,
        },
        {
            "hospital_id": "HOSP-07",
            "name": "Pimpri-Chinchwad General Unit (Synthetic Profile)",
            "area": "Pimpri",
            "city": "Pimpri-Chinchwad",
            "latitude": 18.6210,
            "longitude": 73.8080,
            "priority_level": "normal",
            "bed_capacity": 220,
            "status": "active",
            "is_synthetic_profile": True,
        },
        {
            "hospital_id": "HOSP-08",
            "name": "Swargate Urban Referral Hospital (Synthetic Profile)",
            "area": "Swargate",
            "city": "Pune",
            "latitude": 18.5045,
            "longitude": 73.8585,
            "priority_level": "normal",
            "bed_capacity": 200,
            "status": "active",
            "is_synthetic_profile": True,
        },
    ]


def build_products() -> list[dict[str, Any]]:
    """Define 4 essential emergency medical supplies."""
    return [
        {
            "product_id": "PROD-01",
            "name": "Oxygen Cylinders",
            "category": "Respiratory Support",
            "unit": "cylinder",
            "unit_weight_kg": 18.5,
            "base_transport_cost_per_km": 4.5,
            "cold_chain_required": False,
        },
        {
            "product_id": "PROD-02",
            "name": "IV Fluid Cartons",
            "category": "Fluid Therapy",
            "unit": "carton",
            "unit_weight_kg": 12.0,
            "base_transport_cost_per_km": 2.8,
            "cold_chain_required": False,
        },
        {
            "product_id": "PROD-03",
            "name": "Trauma Kits",
            "category": "Emergency Surgery",
            "unit": "kit",
            "unit_weight_kg": 6.5,
            "base_transport_cost_per_km": 3.2,
            "cold_chain_required": False,
        },
        {
            "product_id": "PROD-04",
            "name": "Essential Medicine Boxes",
            "category": "Pharmaceuticals",
            "unit": "box",
            "unit_weight_kg": 5.0,
            "base_transport_cost_per_km": 2.5,
            "cold_chain_required": True,
        },
    ]


def build_inventory(
    warehouses: list[dict[str, Any]],
    products: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    Generate synthetic warehouse inventory records.

    PROD-01 (Oxygen Cylinders) is intentionally stocked below aggregate
    hospital demand to create a controlled shortage for lexicographic
    priority optimization demonstrations.
    """
    # Controlled baseline stocks per (warehouse_id, product_id)
    stock_matrix: dict[tuple[str, str], int] = {
        # Oxygen Cylinders: total = 150 + 130 + 100 = 380 (controlled shortage vs ~520 demand)
        ("WH-01", "PROD-01"): 150,
        ("WH-02", "PROD-01"): 130,
        ("WH-03", "PROD-01"): 100,
        # IV Fluid Cartons: total = 480 + 420 + 360 = 1260 (adequate supply)
        ("WH-01", "PROD-02"): 480,
        ("WH-02", "PROD-02"): 420,
        ("WH-03", "PROD-02"): 360,
        # Trauma Kits: total = 120 + 100 + 90 = 310 (tight / minor shortage vs ~345 demand)
        ("WH-01", "PROD-03"): 120,
        ("WH-02", "PROD-03"): 100,
        ("WH-03", "PROD-03"): 90,
        # Essential Medicine Boxes: total = 400 + 380 + 320 = 1100 (adequate supply)
        ("WH-01", "PROD-04"): 400,
        ("WH-02", "PROD-04"): 380,
        ("WH-03", "PROD-04"): 320,
    }

    records: list[dict[str, Any]] = []
    record_idx = 1
    for wh in warehouses:
        for prod in products:
            base_qty = stock_matrix[(wh["warehouse_id"], prod["product_id"])]
            # Small deterministic jitter (0 to +5) on adequate products only, keeping shortage guaranteed
            jitter = 0 if prod["product_id"] in {"PROD-01", "PROD-03"} else rng.randint(0, 5)
            available_qty = max(0, base_qty + jitter)
            reserved_qty = 0
            records.append(
                {
                    "inventory_id": f"INV-{record_idx:03d}",
                    "warehouse_id": wh["warehouse_id"],
                    "product_id": prod["product_id"],
                    "quantity_available": available_qty,
                    "quantity_reserved": reserved_qty,
                    "reorder_level": max(20, int(available_qty * 0.2)),
                    "data_note": "Illustrative synthetic stock",
                }
            )
            record_idx += 1
    return records


def build_demands(
    hospitals: list[dict[str, Any]],
    products: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    Generate synthetic hospital demand requests.

    Ensures critical hospitals have elevated emergency requirements and
    establishes controlled supply shortages on Oxygen Cylinders (PROD-01)
    and Trauma Kits (PROD-03).
    """
    priority_demand_baseline: dict[str, dict[str, int]] = {
        "critical": {"PROD-01": 95, "PROD-02": 160, "PROD-03": 60, "PROD-04": 135},
        "high": {"PROD-01": 65, "PROD-02": 120, "PROD-03": 45, "PROD-04": 100},
        "normal": {"PROD-01": 45, "PROD-02": 85, "PROD-03": 30, "PROD-04": 75},
    }

    records: list[dict[str, Any]] = []
    record_idx = 1
    for hosp in hospitals:
        priority = hosp["priority_level"]
        for prod in products:
            base_demand = priority_demand_baseline[priority][prod["product_id"]]
            variation = rng.randint(-4, 6)
            qty_requested = max(10, base_demand + variation)
            records.append(
                {
                    "demand_id": f"DEM-{record_idx:03d}",
                    "hospital_id": hosp["hospital_id"],
                    "product_id": prod["product_id"],
                    "quantity_requested": qty_requested,
                    "priority_level": priority,
                    "status": "open",
                    "data_note": "Illustrative synthetic demand",
                }
            )
            record_idx += 1
    return records


def build_routes(
    warehouses: list[dict[str, Any]],
    hospitals: list[dict[str, Any]],
    rng: random.Random,
) -> list[dict[str, Any]]:
    """
    Generate 24 synthetic warehouse-to-hospital route pairs (3 x 8).

    Distances are derived from Haversine great-circle distance scaled by
    an urban road tortuosity factor. Travel times are synthetic estimates
    and do NOT represent real-time traffic conditions.
    """
    records: list[dict[str, Any]] = []
    route_idx = 1
    for wh in warehouses:
        for hosp in hospitals:
            straight_km = haversine_km(
                wh["latitude"],
                wh["longitude"],
                hosp["latitude"],
                hosp["longitude"],
            )
            # Ensure minimum short-haul distance of 1.2 km within the same locality
            road_distance_km = round(max(1.2, straight_km * ROAD_TORTUOSITY_FACTOR), 2)
            # Synthetic travel time with minor deterministic corridor factor
            corridor_factor = rng.uniform(0.95, 1.15)
            estimated_time_min = round(
                max(5.0, (road_distance_km / AVG_URBAN_SPEED_KMPH) * 60.0 * corridor_factor),
                1,
            )
            base_cost_per_unit = round(12.0 + road_distance_km * 2.4, 2)

            records.append(
                {
                    "route_id": f"RT-{route_idx:03d}",
                    "warehouse_id": wh["warehouse_id"],
                    "hospital_id": hosp["hospital_id"],
                    "distance_km": road_distance_km,
                    "estimated_travel_time_min": estimated_time_min,
                    "base_transport_cost_per_unit": base_cost_per_unit,
                    "is_available": True,
                    "road_condition": "normal",
                    "data_note": "Synthetic estimate; not real-time traffic",
                }
            )
            route_idx += 1
    return records


def write_csv(file_path: Path, rows: list[dict[str, Any]]) -> None:
    """Write a list of dictionaries to a CSV file with UTF-8 encoding."""
    if not rows:
        raise ValueError(f"Cannot write empty dataset to {file_path}")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with file_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_all(output_dir: Path = OUTPUT_DIR, seed: int = RANDOM_SEED) -> dict[str, int]:
    """Generate all six synthetic CSV files and return row counts."""
    rng = random.Random(seed)
    warehouses = build_warehouses()
    hospitals = build_hospitals()
    products = build_products()
    inventory = build_inventory(warehouses, products, rng)
    demands = build_demands(hospitals, products, rng)
    routes = build_routes(warehouses, hospitals, rng)

    datasets = {
        "warehouses.csv": warehouses,
        "hospitals.csv": hospitals,
        "products.csv": products,
        "inventory.csv": inventory,
        "demands.csv": demands,
        "routes.csv": routes,
    }

    counts: dict[str, int] = {}
    for filename, rows in datasets.items():
        write_csv(output_dir / filename, rows)
        counts[filename] = len(rows)

    return counts


def main() -> None:
    counts = generate_all()
    print("MEDILOGIX synthetic dataset generated successfully (seed=42):")
    for filename, count in counts.items():
        print(f"  - {OUTPUT_DIR / filename}: {count} rows")


if __name__ == "__main__":
    main()
