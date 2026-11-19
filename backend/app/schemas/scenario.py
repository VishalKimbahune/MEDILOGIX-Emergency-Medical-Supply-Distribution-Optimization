"""Pydantic v2 schemas for Phase 4C Disaster & Disruption Scenario Simulation."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ScenarioType = Literal[
    "warehouse_outage",
    "warehouse_failure",
    "road_closure",
    "demand_spike",
    "demand_surge",
    "vehicle_unavailability",
    "combined",
    "custom",
]


class ScenarioCreate(BaseModel):
    """Create a saved scenario definition."""

    name: str = Field(..., min_length=3, max_length=120)
    description: str | None = None
    scenario_type: ScenarioType = "combined"
    parameters_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ScenarioResponse(ScenarioCreate):
    """Saved scenario record."""

    id: int

    model_config = ConfigDict(from_attributes=True)


class ScenarioSimulationRequest(BaseModel):
    """Request payload to execute an isolated disaster simulation against a baseline run."""

    baseline_run_id: int = Field(..., gt=0)
    name: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = None
    scenario_type: ScenarioType = "combined"
    disabled_warehouse_codes: list[str] = Field(default_factory=list)
    closed_route_codes: list[str] = Field(default_factory=list)
    closed_way_ids: list[int] = Field(default_factory=list)
    demand_spike_hospital_codes: list[str] = Field(default_factory=list)
    demand_spike_pct: float = Field(default=0.0, ge=0.0, le=300.0)
    disabled_vehicle_codes: list[str] = Field(default_factory=list)
    routing_objective: Literal["min_distance", "min_time"] = "min_distance"
    allow_multi_trip: bool = True
    max_trips_per_vehicle: int = Field(default=3, ge=1, le=10)
    allow_split_deliveries: bool = True


class ScenarioMetricsSnapshot(BaseModel):
    """Structured KPI snapshot for either baseline or disrupted simulation state."""

    solver_status: str
    routing_status: str
    total_demand: float
    total_allocated: float
    total_unmet_demand: float
    fulfillment_percentage: float
    critical_fulfillment_pct: float
    high_fulfillment_pct: float
    normal_fulfillment_pct: float
    total_transport_cost: float
    total_route_distance_km: float
    estimated_route_duration_min: float
    available_vehicles_count: int
    completed_feasible_routes: int
    infeasibility_reasons: list[str] = Field(default_factory=list)


class ScenarioRunSummaryResponse(BaseModel):
    """Summary schema for scenario simulation history."""

    id: int
    simulation_code: str
    scenario_id: int
    scenario_name: str
    scenario_type: str
    baseline_run_id: int
    baseline_run_code: str | None = None
    status: str
    execution_time_ms: float
    baseline_metrics: ScenarioMetricsSnapshot
    disrupted_metrics: ScenarioMetricsSnapshot
    created_at: datetime


class ScenarioRunDetailResponse(ScenarioRunSummaryResponse):
    """Complete scenario simulation response including deltas, routes, and closures."""

    description: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    disrupted_routes: list[dict[str, Any]] = Field(default_factory=list)
    closed_corridors: list[dict[str, Any]] = Field(default_factory=list)
    closed_way_ids: list[int] = Field(default_factory=list)
    closed_osm_ways: list[dict[str, Any]] = Field(default_factory=list)
    disabled_warehouses: list[str] = Field(default_factory=list)
    unreachable_hospitals: list[str] = Field(default_factory=list)
    routing_source: str = "synthetic_fallback"
    routing_objective: str = "min_distance"
    fallback_warning: str | None = None
    notes: str | None = None
