"""Demand ORM model representing hospital medical supply requests."""

from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Demand(Base, TimestampMixin):
    """Hospital supply demand request for a specific medical product."""

    __tablename__ = "demands"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    demand_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
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
    )  # open | partially_fulfilled | fulfilled | cancelled
    data_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Relationships
    hospital = relationship("Hospital", back_populates="demands")
    product = relationship("Product", back_populates="demands")
