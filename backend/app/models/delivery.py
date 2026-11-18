"""Delivery ORM model tracking dispatched routes derived from optimization runs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Delivery(Base, TimestampMixin):
    """Planned or dispatched delivery route linking a warehouse and hospital(s)."""

    __tablename__ = "deliveries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    optimization_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("optimization_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    vehicle_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("vehicles.id", ondelete="SET NULL"), index=True, nullable=True
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    hospital_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hospitals.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    route_distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_duration_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="planned"
    )  # planned | dispatched | in_transit | delivered | cancelled
    route_sequence_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)

    # Relationships
    optimization_run = relationship("OptimizationRun", back_populates="deliveries")
    vehicle = relationship("Vehicle", back_populates="deliveries")
    warehouse = relationship("Warehouse", back_populates="deliveries")
    hospital = relationship("Hospital", back_populates="deliveries")
