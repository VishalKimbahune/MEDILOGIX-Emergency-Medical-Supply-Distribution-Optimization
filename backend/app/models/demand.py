"""Demand ORM model representing hospital medical supply requests."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Demand(Base, TimestampMixin):
    """Hospital supply demand request / order line for a specific medical product."""

    __tablename__ = "demands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    demand_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    order_group_code: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    hospital_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), index=True, nullable=False
    )
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_level: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False, default="normal"
    )  # critical | high | normal
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="open"
    )  # pending_approval | open | partially_fulfilled | fulfilled | rejected | cancelled
    approval_status: Mapped[str | None] = mapped_column(
        String(32), index=True, nullable=True, default="approved"
    )  # pending_approval | approved | rejected
    emergency_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    required_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Relationships
    hospital = relationship("Hospital", back_populates="demands")
    product = relationship("Product", back_populates="demands")
