"""Warehouse ORM model representing fictional medical distribution hubs."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Warehouse(Base, TimestampMixin):
    """Medical supply distribution warehouse (simulation hub)."""

    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    area: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, default="Pune")
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    storage_capacity_units: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="active")
    is_synthetic_hub: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    inventory_items = relationship("Inventory", back_populates="warehouse", cascade="all, delete-orphan")
    outgoing_roads = relationship("Road", back_populates="warehouse", cascade="all, delete-orphan")
    vehicles = relationship("Vehicle", back_populates="warehouse", cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="warehouse")
    deliveries = relationship("Delivery", back_populates="warehouse")
