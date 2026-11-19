"""
Append-Only Audit Logging & Targeted Role Notification Service.

Security rules:
- Never logs passwords, JWTs, refresh tokens, reset tokens, or secret keys.
- Audit records are append-only from application interfaces.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.platform import AuditLog, Notification
from app.models.user import User

SENSITIVE_KEYS = {
    "password",
    "new_password",
    "confirm_password",
    "hashed_password",
    "token",
    "access_token",
    "refresh_token",
    "reset_token",
    "secret",
    "authorization",
}


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively strip any sensitive secret/password/token keys before persisting audit metadata."""
    if not metadata:
        return {}
    clean: dict[str, Any] = {}
    for k, v in metadata.items():
        if str(k).lower() in SENSITIVE_KEYS:
            clean[k] = "[REDACTED]"
        elif isinstance(v, dict):
            clean[k] = _sanitize_metadata(v)
        else:
            clean[k] = v
    return clean


def log_audit_event(
    db: Session,
    *,
    action: str,
    target_entity: str,
    target_id: str | int | None = None,
    actor: User | None = None,
    actor_email: str | None = None,
    actor_role: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    commit: bool = False,
) -> AuditLog:
    """Append an immutable audit log entry (caller commits transaction unless commit=True)."""
    entry = AuditLog(
        actor_user_id=actor.id if actor else None,
        actor_email=(actor.email if actor else actor_email),
        actor_role=(actor.role if actor else actor_role),
        action=action,
        target_entity=target_entity,
        target_id=str(target_id) if target_id is not None else None,
        metadata_json=_sanitize_metadata(metadata),
        ip_address=ip_address,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry


def create_notification(
    db: Session,
    *,
    user_id: int,
    title: str,
    message: str,
    category: str = "system",
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> Notification:
    """Create a targeted notification for a specific user."""
    notif = Notification(
        user_id=user_id,
        title=title[:160],
        message=message,
        category=category,
        entity_type=entity_type,
        entity_id=entity_id,
        is_read=False,
    )
    db.add(notif)
    return notif


def notify_users_by_role(
    db: Session,
    *,
    role: str,
    title: str,
    message: str,
    category: str = "system",
    entity_type: str | None = None,
    entity_id: int | None = None,
    hospital_id: int | None = None,
    warehouse_id: int | None = None,
) -> int:
    """Send targeted notifications to all active approved users matching role & optional org scope."""
    stmt = select(User).where(
        User.role == role,
        User.is_active.is_(True),
        User.is_approved.is_(True),
    )
    if hospital_id is not None:
        stmt = stmt.where(User.associated_hospital_id == hospital_id)
    if warehouse_id is not None:
        stmt = stmt.where(User.associated_warehouse_id == warehouse_id)

    recipients = list(db.scalars(stmt).all())
    for user in recipients:
        create_notification(
            db,
            user_id=user.id,
            title=title,
            message=message,
            category=category,
            entity_type=entity_type,
            entity_id=entity_id,
        )
    return len(recipients)
