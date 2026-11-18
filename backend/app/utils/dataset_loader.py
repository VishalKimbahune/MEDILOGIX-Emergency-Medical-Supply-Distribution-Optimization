"""
Dataset Loader & Database Seeder for MEDILOGIX.

Reads the six generated synthetic CSV files from data/synthetic/ and seeds
the relational database idempotently (skipping records that already exist).
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.models.hospital import Hospital
from app.models.inventory import Inventory
from app.models.product import Product
from app.models.road import Road
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _read_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def seed_database_from_csv(session: Session, data_dir: Path) -> dict[str, int]:
    """
    Idempotently load synthetic CSV datasets into SQLAlchemy tables.

    Returns:
        Dictionary mapping entity table names to newly inserted row counts.
    """
    inserted: dict[str, int] = {
        "warehouses": 0,
        "hospitals": 0,
        "products": 0,
        "inventory": 0,
        "demands": 0,
        "roads": 0,
        "vehicles": 0,
    }

    # 1. Warehouses
    for row in _read_csv_rows(data_dir / "warehouses.csv"):
        existing = session.scalar(select(Warehouse).where(Warehouse.code == row["warehouse_id"]))
        if not existing:
            session.add(
                Warehouse(
                    code=row["warehouse_id"],
                    name=row["name"],
                    area=row["area"],
                    city=row["city"],
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    storage_capacity_units=int(row["storage_capacity_units"]),
                    status=row["status"],
                    is_synthetic_hub=_parse_bool(row["is_synthetic_hub"]),
                )
            )
            inserted["warehouses"] += 1
    session.flush()

    # 2. Hospitals
    for row in _read_csv_rows(data_dir / "hospitals.csv"):
        existing = session.scalar(select(Hospital).where(Hospital.code == row["hospital_id"]))
        if not existing:
            session.add(
                Hospital(
                    code=row["hospital_id"],
                    name=row["name"],
                    area=row["area"],
                    city=row["city"],
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    priority_level=row["priority_level"],
                    bed_capacity=int(row["bed_capacity"]),
                    status=row["status"],
                    is_synthetic_profile=_parse_bool(row["is_synthetic_profile"]),
                )
            )
            inserted["hospitals"] += 1
    session.flush()

    # 3. Products
    for row in _read_csv_rows(data_dir / "products.csv"):
        existing = session.scalar(select(Product).where(Product.code == row["product_id"]))
        if not existing:
            session.add(
                Product(
                    code=row["product_id"],
                    name=row["name"],
                    category=row["category"],
                    unit=row["unit"],
                    unit_weight_kg=float(row["unit_weight_kg"]),
                    base_transport_cost_per_km=float(row["base_transport_cost_per_km"]),
                    cold_chain_required=_parse_bool(row["cold_chain_required"]),
                )
            )
            inserted["products"] += 1
    session.flush()

    # Build code -> primary key lookup maps
    wh_map = {wh.code: wh.id for wh in session.scalars(select(Warehouse)).all()}
    hosp_map = {h.code: h.id for h in session.scalars(select(Hospital)).all()}
    prod_map = {p.code: p.id for p in session.scalars(select(Product)).all()}

    # 4. Inventory
    for row in _read_csv_rows(data_dir / "inventory.csv"):
        existing = session.scalar(
            select(Inventory).where(Inventory.inventory_code == row["inventory_id"])
        )
        if not existing:
            session.add(
                Inventory(
                    inventory_code=row["inventory_id"],
                    warehouse_id=wh_map[row["warehouse_id"]],
                    product_id=prod_map[row["product_id"]],
                    quantity_available=int(row["quantity_available"]),
                    quantity_reserved=int(row["quantity_reserved"]),
                    reorder_level=int(row["reorder_level"]),
                    data_note=row.get("data_note"),
                )
            )
            inserted["inventory"] += 1

    # 5. Demands
    for row in _read_csv_rows(data_dir / "demands.csv"):
        existing = session.scalar(select(Demand).where(Demand.demand_code == row["demand_id"]))
        if not existing:
            session.add(
                Demand(
                    demand_code=row["demand_id"],
                    hospital_id=hosp_map[row["hospital_id"]],
                    product_id=prod_map[row["product_id"]],
                    quantity_requested=int(row["quantity_requested"]),
                    priority_level=row["priority_level"],
                    status=row["status"],
                    data_note=row.get("data_note"),
                )
            )
            inserted["demands"] += 1

    # 6. Roads / Routes
    for row in _read_csv_rows(data_dir / "routes.csv"):
        existing = session.scalar(select(Road).where(Road.route_code == row["route_id"]))
        if not existing:
            session.add(
                Road(
                    route_code=row["route_id"],
                    warehouse_id=wh_map[row["warehouse_id"]],
                    hospital_id=hosp_map[row["hospital_id"]],
                    distance_km=float(row["distance_km"]),
                    estimated_travel_time_min=float(row["estimated_travel_time_min"]),
                    base_transport_cost_per_unit=float(row["base_transport_cost_per_unit"]),
                    is_available=_parse_bool(row["is_available"]),
                    road_condition=row["road_condition"],
                    data_note=row.get("data_note"),
                )
            )
            inserted["roads"] += 1

    # 7. Default starter fleet vehicles (2 per simulation hub) for future VRP module
    for wh_code, wh_id in sorted(wh_map.items()):
        for idx in (1, 2):
            v_code = f"VEH-{wh_code}-{idx:02d}"
            existing = session.scalar(select(Vehicle).where(Vehicle.vehicle_code == v_code))
            if not existing:
                session.add(
                    Vehicle(
                        vehicle_code=v_code,
                        warehouse_id=wh_id,
                        vehicle_type="emergency_refrigerated_van" if idx == 1 else "medical_truck",
                        capacity_kg=1800.0 if idx == 1 else 3200.0,
                        status="available",
                    )
                )
                inserted["vehicles"] += 1

    session.commit()
    return inserted
