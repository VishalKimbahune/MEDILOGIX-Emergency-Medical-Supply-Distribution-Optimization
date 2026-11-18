"""Vehicle ORM model for fleet capacity and VRP extensions."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Vehicle(Base, TimestampMixin):
    """Delivery vehicle stationed at a medical distribution warehouse."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    vehicle_type: Mapped[str] = mapped_column(String(64), nullable=False, default="medical_van")
    capacity_kg: Mapped[float] = mapped_column(Float, nullable=False, default=1500.0)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="available")

    # Relationships
    warehouse = relationship("Warehouse", back_populates="vehicles")
    deliveries = relationship("Delivery", back_populates="vehicle")
