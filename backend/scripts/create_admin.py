"""
MEDILOGIX Safe Initial Admin Bootstrap CLI.

Usage:
    python scripts/create_admin.py --email admin@medilogix.org --name "System Administrator"
    # Or via environment variables:
    MEDILOGIX_ADMIN_EMAIL=... MEDILOGIX_ADMIN_PASSWORD=... python scripts/create_admin.py

Never hardcodes credentials in source code or frontend bundles.
Safely applies additive schema migrations without modifying existing operational records.
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
from app.models.user import User  # noqa: E402
from app.services import audit_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote an initial MEDILOGIX Admin account.")
    parser.add_argument("--email", default=os.getenv("MEDILOGIX_ADMIN_EMAIL", ""), help="Admin email address")
    parser.add_argument("--name", default=os.getenv("MEDILOGIX_ADMIN_NAME", "MEDILOGIX System Admin"), help="Full name")
    parser.add_argument("--phone", default=os.getenv("MEDILOGIX_ADMIN_PHONE", ""), help="Optional phone number")
    parser.add_argument(
        "--password",
        default=os.getenv("MEDILOGIX_ADMIN_PASSWORD", ""),
        help="Admin password (omit to enter securely via interactive prompt)",
    )
    parser.add_argument(
        "--update-if-exists",
        action="store_true",
        help="Update password/role/status if a user with this email already exists.",
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    if not email:
        email = input("Admin email: ").strip().lower()
    if not email or "@" not in email:
        print("Error: A valid admin email address is required.", file=sys.stderr)
        return 1

    password = args.password
    if not password:
        password = getpass.getpass("Admin password (min 10 chars, upper, lower, digit, symbol): ")
        confirm = getpass.getpass("Confirm admin password: ")
        if password != confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            return 1

    pw_err = validate_password_strength(password)
    if pw_err:
        print(f"Error: {pw_err}", file=sys.stderr)
        return 1

    # Ensure tables and additive columns exist without mutating operational records
    Base.metadata.create_all(bind=engine)
    ensure_additive_columns(engine)

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == email))
        if existing:
            if not args.update_if_exists:
                print(
                    f"User '{email}' already exists (id={existing.id}, role={existing.role}, "
                    f"status={existing.approval_status}). Pass --update-if-exists to update."
                )
                return 0
            existing.full_name = args.name.strip() or existing.full_name
            existing.role = "admin"
            existing.is_active = True
            existing.is_verified = True
            existing.is_approved = True
            existing.approval_status = "approved"
            existing.hashed_password = hash_password(password)
            if args.phone:
                existing.phone_number = args.phone.strip()
            audit_service.log_audit_event(
                db,
                actor=existing,
                action="admin.cli_updated",
                target_entity="user",
                target_id=existing.id,
                metadata={"email": email},
            )
            db.commit()
            print(f"Updated existing Admin account '{email}' (id={existing.id}).")
            return 0

        admin_user = User(
            email=email,
            full_name=args.name.strip() or "MEDILOGIX System Admin",
            phone_number=args.phone.strip() or None,
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
            is_verified=True,
            is_approved=True,
            approval_status="approved",
        )
        db.add(admin_user)
        db.flush()
        audit_service.log_audit_event(
            db,
            actor=admin_user,
            action="admin.cli_created",
            target_entity="user",
            target_id=admin_user.id,
            metadata={"email": email},
        )
        db.commit()
        print(f"Created MEDILOGIX Admin account '{email}' (id={admin_user.id}).")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
