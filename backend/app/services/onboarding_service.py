"""
Onboarding & Network Synchronization Service.

Handles safe code generation, automatic corridor generation (Road table), and
activation of newly registered Hospitals, Warehouses, and Delivery Vehicles
when an Administrator approves a pending registration.
"""

from __future__ import annotations

import math
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.models.road import Road
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute geodesic distance in kilometers between two WGS84 coordinates."""
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))


def generate_next_code(existing_codes: list[str], prefix: str, pad: int = 2) -> str:
    """Generate the next unique sequential code like HOSP-09, WH-04, or RTE-025."""
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$", re.IGNORECASE)
    max_num = 0
    existing_set = {c.upper() for c in existing_codes}
    for code in existing_codes:
        m = pattern.match(code.strip())
        if m:
            max_num = max(max_num, int(m.group(1)))
    candidate_num = max_num + 1
    while True:
        candidate = f"{prefix}-{candidate_num:0{pad}d}".upper()
        if candidate not in existing_set:
            return candidate
        candidate_num += 1


def _create_road_corridor(
    db: Session,
    warehouse: Warehouse,
    hospital: Hospital,
    existing_route_codes: set[str],
) -> Road:
    """Create a realistic Pune urban corridor connecting a warehouse and hospital."""
    crow_km = haversine_km(
        warehouse.latitude,
        warehouse.longitude,
        hospital.latitude,
        hospital.longitude,
    )
    road_km = round(max(1.5, crow_km * 1.28), 2)
    # Estimated urban medical corridor speed ~28 km/h
    travel_min = round(max(5.0, (road_km / 28.0) * 60.0), 1)
    base_cost = round(12.0 + road_km * 1.4, 2)

    route_code = generate_next_code(list(existing_route_codes), "RTE", pad=3)
    existing_route_codes.add(route_code)

    road = Road(
        route_code=route_code,
        warehouse_id=warehouse.id,
        hospital_id=hospital.id,
        distance_km=road_km,
        estimated_travel_time_min=travel_min,
        base_transport_cost_per_unit=base_cost,
        is_available=True,
        road_condition="normal",
        data_note="Auto-generated corridor upon facility onboarding approval",
    )
    db.add(road)
    return road


def ensure_road_corridors_for_hospital(db: Session, hospital: Hospital) -> int:
    """Create missing warehouse -> hospital Road corridors for a newly activated hospital."""
    warehouses = list(db.scalars(select(Warehouse)).all())
    existing_pairs = {
        (r.warehouse_id, r.hospital_id) for r in db.scalars(select(Road)).all()
    }
    existing_codes = {r.route_code.upper() for r in db.scalars(select(Road)).all()}
    created = 0
    for wh in warehouses:
        if (wh.id, hospital.id) not in existing_pairs:
            _create_road_corridor(db, wh, hospital, existing_codes)
            existing_pairs.add((wh.id, hospital.id))
            created += 1
    return created


def ensure_road_corridors_for_warehouse(db: Session, warehouse: Warehouse) -> int:
    """Create missing warehouse -> hospital Road corridors for a newly activated warehouse."""
    hospitals = list(db.scalars(select(Hospital)).all())
    existing_pairs = {
        (r.warehouse_id, r.hospital_id) for r in db.scalars(select(Road)).all()
    }
    existing_codes = {r.route_code.upper() for r in db.scalars(select(Road)).all()}
    created = 0
    for hosp in hospitals:
        if (warehouse.id, hosp.id) not in existing_pairs:
            _create_road_corridor(db, warehouse, hosp, existing_codes)
            existing_pairs.add((warehouse.id, hosp.id))
            created += 1
    return created


def activate_onboarded_entities_for_user(db: Session, user: User) -> dict[str, Any]:
    """
    Activate any newly onboarded Hospital, Warehouse, or Delivery Vehicle linked to a user
    when an Administrator approves their registration, and ensure full road connectivity.
    """
    summary: dict[str, Any] = {
        "activated_hospital_code": None,
        "activated_warehouse_code": None,
        "activated_vehicle_codes": [],
        "roads_created": 0,
    }

    if user.role == "hospital" and user.associated_hospital_id:
        hosp = db.get(Hospital, user.associated_hospital_id)
        if hosp:
            if hosp.status != "active":
                hosp.status = "active"
                summary["activated_hospital_code"] = hosp.code
            summary["roads_created"] += ensure_road_corridors_for_hospital(db, hosp)

    elif user.role == "warehouse" and user.associated_warehouse_id:
        wh = db.get(Warehouse, user.associated_warehouse_id)
        if wh:
            if wh.status != "active":
                wh.status = "active"
                summary["activated_warehouse_code"] = wh.code
            summary["roads_created"] += ensure_road_corridors_for_warehouse(db, wh)

    elif user.role == "delivery":
        vehicles = list(
            db.scalars(
                select(Vehicle).where(Vehicle.assigned_driver_user_id == user.id)
            ).all()
        )
        for veh in vehicles:
            if veh.status == "unavailable":
                veh.status = "available"
                summary["activated_vehicle_codes"].append(veh.vehicle_code)

    return summary
