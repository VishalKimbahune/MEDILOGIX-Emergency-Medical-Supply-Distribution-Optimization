"""
MEDILOGIX Optional Development Demo Accounts Seeder.

Creates clearly labeled local development accounts for all 4 portals (Admin, Hospital,
Warehouse, Delivery) linked to existing seeded Pune facilities (HOSP-01, WH-01, VEH-WH-01-01).

Usage:
    python scripts/seed_demo_accounts.py --password "YourStrongDevPassword!1"

SECURITY NOTE:
- Never run this in production with weak or shared passwords.
- Never embed these credentials in frontend source code.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app import models as _models  # noqa: E402, F401
from app.core.security import hash_password, validate_password_strength  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.connection import SessionLocal, engine  # noqa: E402
from app.database.migrations import ensure_additive_columns  # noqa: E402
from app.models.hospital import Hospital  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.vehicle import Vehicle  # noqa: E402
from app.models.warehouse import Warehouse  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed optional local dev demo accounts for MEDILOGIX portals.")
    parser.add_argument(
        "--password",
        default=os.getenv("MEDILOGIX_DEMO_PASSWORD", "Medilogix@2026"),
        help="Password to assign to created demo accounts (defaults to Medilogix@2026 for local dev).",
    )
    args = parser.parse_args()

    password = args.password

    pw_err = validate_password_strength(password)
    if pw_err:
        print(f"Error: {pw_err}", file=sys.stderr)
        return 1

    Base.metadata.create_all(bind=engine)
    ensure_additive_columns(engine)

    with SessionLocal() as db:
        hosp = db.scalar(select(Hospital).order_by(Hospital.code))
        wh = db.scalar(select(Warehouse).order_by(Warehouse.code))
        veh = db.scalar(select(Vehicle).order_by(Vehicle.vehicle_code))

        specs = [
            {
                "email": "admin.dev@medilogix.org",
                "full_name": "Dev System Administrator",
                "role": "admin",
                "hospital_id": None,
                "warehouse_id": None,
            },
            {
                "email": "hospital.dev@medilogix.org",
                "full_name": f"Dev Coordinator ({hosp.code if hosp else 'Hospital'})",
                "role": "hospital",
                "hospital_id": hosp.id if hosp else None,
                "warehouse_id": None,
            },
            {
                "email": "warehouse.dev@medilogix.org",
                "full_name": f"Dev Manager ({wh.code if wh else 'Warehouse'})",
                "role": "warehouse",
                "hospital_id": None,
                "warehouse_id": wh.id if wh else None,
            },
            {
                "email": "delivery.dev@medilogix.org",
                "full_name": "Dev Fleet Driver (Pune)",
                "role": "delivery",
                "hospital_id": None,
                "warehouse_id": None,
            },
        ]

        pw_hash = hash_password(password)
        driver_user: User | None = None

        for spec in specs:
            existing = db.scalar(select(User).where(User.email == spec["email"]))
            if existing:
                print(f"[SKIP] {spec['email']} already exists (role={existing.role}).")
                if existing.role == "delivery":
                    driver_user = existing
                continue
            user = User(
                email=spec["email"],
                full_name=spec["full_name"],
                hashed_password=pw_hash,
                role=spec["role"],
                is_active=True,
                is_verified=True,
                is_approved=True,
                approval_status="approved",
                associated_hospital_id=spec["hospital_id"],
                associated_warehouse_id=spec["warehouse_id"],
            )
            db.add(user)
            db.flush()
            if user.role == "delivery":
                driver_user = user
            print(f"[CREATED] {user.email} (role={user.role})")

        if driver_user and veh and veh.assigned_driver_user_id is None:
            veh.assigned_driver_user_id = driver_user.id
            print(f"[ASSIGNED] Vehicle {veh.vehicle_code} -> {driver_user.email}")

        db.commit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
