"""Allocation ORM model persisting solved x[i,j,k] and u[j,k] outcomes."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Allocation(Base, TimestampMixin):
    """Optimal shipment allocation of product k from warehouse i to hospital j."""

    __tablename__ = "allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    optimization_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("optimization_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    hospital_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hospitals.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    quantity_allocated: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unmet_quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    transport_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Relationships
    optimization_run = relationship("OptimizationRun", back_populates="allocations")
    warehouse = relationship("Warehouse", back_populates="allocations")
    hospital = relationship("Hospital", back_populates="allocations")
    product = relationship("Product", back_populates="allocations")
