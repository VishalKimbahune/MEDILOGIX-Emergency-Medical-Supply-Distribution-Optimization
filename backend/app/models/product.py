"""Product ORM model representing essential medical supplies."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Product(Base, TimestampMixin):
    """Essential medical supply item tracked across the logistics network."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_weight_kg: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    base_transport_cost_per_km: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    cold_chain_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    inventory_items = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")
    demands = relationship("Demand", back_populates="product", cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="product")
