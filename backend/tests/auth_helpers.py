"""Shared authentication helpers for isolated backend test suites."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.models.user import User


def attach_admin_auth(client: TestClient, session_factory: Any) -> User:
    """Seed an isolated active Admin user and attach a genuine Bearer JWT to the TestClient."""
    with session_factory() as db:
        admin = User(
            email="test.admin@medilogix.org",
            full_name="Test Admin",
            hashed_password=hash_password("TestAdminPass!2026"),
            role="admin",
            is_active=True,
            is_verified=True,
            is_approved=True,
            approval_status="approved",
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        token, _ = create_access_token(user_id=admin.id, role=admin.role, email=admin.email)
        client.headers["Authorization"] = f"Bearer {token}"
        return admin
