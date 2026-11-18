"""OptimizationRun ORM model recording OR solver executions and KPIs."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class OptimizationRun(Base, TimestampMixin):
    """Audit record of an Operations Research optimization run."""

    __tablename__ = "optimization_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_code: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    model_type: Mapped[str] = mapped_column(
        String(48), index=True, nullable=False
    )  # transportation_lp | lexicographic_priority
    scenario_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("scenarios.id", ondelete="SET NULL"), index=True, nullable=True
    )
    solver_status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_allocated: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_unmet_demand: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    execution_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    scenario = relationship("Scenario", back_populates="optimization_runs")
    allocations = relationship(
        "Allocation", back_populates="optimization_run", cascade="all, delete-orphan"
    )
    deliveries = relationship(
        "Delivery", back_populates="optimization_run", cascade="all, delete-orphan"
    )
