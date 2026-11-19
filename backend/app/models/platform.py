"""
Platform Governance & Traceability ORM Models:
- Notification: Targeted role/user notifications for orders, dispatches, deliveries & approvals
- AuditLog: Append-only audit trail for security & operational actions (zero secrets logged)
- StockMovement: Traceable warehouse stock-in and controlled adjustment history
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow


class Notification(Base):
    """Targeted in-app notification for an authenticated user."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(
        String(48), index=True, nullable=False, default="system"
    )  # order | optimization | dispatch | delivery | warehouse | account | system
    entity_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, index=True, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    user = relationship("User", back_populates="notifications")


class AuditLog(Base):
    """Append-only operational and security audit event record."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    target_entity: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    actor = relationship("User")


class StockMovement(Base):
    """Traceable warehouse stock-in or controlled adjustment record."""

    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    inventory_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("inventory.id", ondelete="CASCADE"), index=True, nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    actor_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    movement_type: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="adjustment"
    )  # stock_in | adjustment | reorder_update
    quantity_delta: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True, nullable=False
    )

    inventory = relationship("Inventory")
    warehouse = relationship("Warehouse")
    product = relationship("Product")
    actor = relationship("User")
