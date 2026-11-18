"""Road / Route ORM model connecting warehouses and hospitals."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Road(Base, TimestampMixin):
    """Corridor edge between a warehouse and a hospital (synthetic distance/time)."""

    __tablename__ = "roads"
    __table_args__ = (
        UniqueConstraint("warehouse_id", "hospital_id", name="uq_road_warehouse_hospital"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    route_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="CASCADE"), index=True, nullable=False
    )
    hospital_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hospitals.id", ondelete="CASCADE"), index=True, nullable=False
    )
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_travel_time_min: Mapped[float] = mapped_column(Float, nullable=False)
    base_transport_cost_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, index=True, nullable=False, default=True)
    road_condition: Mapped[str] = mapped_column(String(40), nullable=False, default="normal")
    data_note: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Relationships
    warehouse = relationship("Warehouse", back_populates="outgoing_roads")
    hospital = relationship("Hospital", back_populates="incoming_roads")
