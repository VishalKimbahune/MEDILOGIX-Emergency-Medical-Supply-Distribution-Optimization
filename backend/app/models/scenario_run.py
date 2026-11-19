"""
Scenario Simulation Run ORM model (Phase 4C).

Persists reproducible disaster simulation snapshots and baseline-versus-disrupted
comparisons without mutating live operational tables or baseline optimization runs.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class ScenarioRun(Base, TimestampMixin):
    """Persisted execution record of a disaster/disruption scenario simulation."""

    __tablename__ = "scenario_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_code: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    scenario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("scenarios.id", ondelete="CASCADE"), index=True, nullable=False
    )
    baseline_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("optimization_runs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False, default="completed")
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    baseline_metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    disrupted_metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    comparison_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    disrupted_routes_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Relationships
    scenario = relationship("Scenario")
    baseline_run = relationship("OptimizationRun")
