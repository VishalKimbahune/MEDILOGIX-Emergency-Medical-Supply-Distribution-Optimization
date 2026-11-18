"""Hospital ORM model representing synthetic hospital demand nodes."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Hospital(Base, TimestampMixin):
    """Hospital facility receiving emergency medical supplies."""

    __tablename__ = "hospitals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    area: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, default="Pune")
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    priority_level: Mapped[str] = mapped_column(
        String(20), index=True, nullable=False, default="normal"
    )  # critical | high | normal
    bed_capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="active")
    is_synthetic_profile: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    demands = relationship("Demand", back_populates="hospital", cascade="all, delete-orphan")
    incoming_roads = relationship("Road", back_populates="hospital", cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="hospital")
    deliveries = relationship("Delivery", back_populates="hospital")
