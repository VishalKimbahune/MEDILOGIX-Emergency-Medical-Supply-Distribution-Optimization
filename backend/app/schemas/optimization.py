"""Pydantic v2 schemas for Operations Research optimization endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OptimizationRequest(BaseModel):
    """Request parameters for executing an OR allocation model."""

    model_type: Literal["transportation_lp", "lexicographic_priority"] = "lexicographic_priority"
    scenario_id: int | None = None
    enforce_route_availability: bool = True
    use_vehicle_capacity: bool = False
    disabled_warehouse_codes: list[str] = Field(default_factory=list)
    closed_route_codes: list[str] = Field(default_factory=list)
    demand_multiplier: float = Field(default=1.0, gt=0.0, le=5.0)


class AllocationItem(BaseModel):
    """Single solved allocation x[i,j,k]."""

    warehouse_code: str
    hospital_code: str
    product_code: str
    quantity_allocated: float
    unit_cost: float
    transport_cost: float


class UnmetDemandItem(BaseModel):
    """Single solved unmet-demand variable u[j,k]."""

    hospital_code: str
    priority_level: str
    product_code: str
    quantity_requested: float
    quantity_allocated: float
    unmet_quantity: float


class OptimizationResultResponse(BaseModel):
    """Structured response returned by optimization endpoints."""

    run_code: str
    model_type: str
    solver_status: str
    total_cost: float
    total_allocated: float
    total_unmet_demand: float
    tier_unmet_fractions: dict[str, float] = Field(default_factory=dict)
    execution_time_ms: float
    allocations: list[AllocationItem] = Field(default_factory=list)
    unmet_demands: list[UnmetDemandItem] = Field(default_factory=list)
    notes: str | None = None


class OptimizationRunSummary(BaseModel):
    """Summary schema for persisted optimization run history."""

    id: int
    run_code: str
    model_type: str
    scenario_id: int | None
    solver_status: str
    total_cost: float
    total_allocated: float
    total_unmet_demand: float
    execution_time_ms: float
    summary_json: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
