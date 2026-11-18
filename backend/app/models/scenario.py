"""Scenario ORM model storing disaster simulation configurations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Scenario(Base, TimestampMixin):
    """Disaster scenario definition (warehouse outage, road closure, demand surge)."""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scenario_type: Mapped[str] = mapped_column(
        String(40), index=True, nullable=False, default="custom"
    )  # warehouse_failure | road_closure | demand_surge | combined | custom
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    optimization_runs = relationship("OptimizationRun", back_populates="scenario")
