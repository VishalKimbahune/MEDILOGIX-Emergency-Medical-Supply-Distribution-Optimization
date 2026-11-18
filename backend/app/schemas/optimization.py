"""Pydantic v2 schemas for Operations Research optimization endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class OptimizationRequest(BaseModel):
    """Request parameters for executing an OR allocation model."""

    model_type: Literal["transportation_lp", "lexicographic_priority"] = "lexicographic_priority"
    warehouse_codes: list[str] | None = Field(
        default=None, description="Optional subset of active warehouse codes to include."
    )
    hospital_codes: list[str] | None = Field(
        default=None, description="Optional subset of active hospital codes to include."
    )
    product_codes: list[str] | None = Field(
        default=None, description="Optional subset of medical product codes to include."
    )
    scenario_id: int | None = None
    enforce_route_availability: bool = True
    allow_unmet_demand: bool = True
    use_vehicle_capacity: bool = False
    disabled_warehouse_codes: list[str] = Field(default_factory=list)
    closed_route_codes: list[str] = Field(default_factory=list)
    demand_multiplier: float = Field(default=1.0, gt=0.0, le=5.0)


class AllocationItem(BaseModel):
    """Single solved planned allocation x[i,j,k]."""

    warehouse_code: str
    warehouse_name: str | None = None
    hospital_code: str
    hospital_name: str | None = None
    hospital_priority: str | None = None
    product_code: str
    product_name: str | None = None
    product_unit: str | None = None
    quantity_allocated: float
    unit_cost: float
    transport_cost: float
    route_code: str | None = None
    distance_km: float | None = None
    estimated_travel_time_min: float | None = None


class UnmetDemandItem(BaseModel):
    """Single solved unmet-demand variable u[j,k]."""

    hospital_code: str
    hospital_name: str | None = None
    priority_level: str
    product_code: str
    product_name: str | None = None
    quantity_requested: float
    quantity_allocated: float
    unmet_quantity: float


class PriorityTierSummary(BaseModel):
    """Fulfillment and unmet-demand analytics per hospital priority tier."""

    priority_level: str
    hospital_count: int
    total_demand: float
    total_allocated: float
    total_unmet: float
    unmet_fraction: float
    fulfillment_pct: float


class WarehouseUtilizationItem(BaseModel):
    """Planned inventory utilization per warehouse (does not alter actual stock)."""

    warehouse_code: str
    warehouse_name: str
    available_stock: float
    allocated_quantity: float
    remaining_stock: float
    utilization_pct: float
    transport_cost: float


class ProductSummaryItem(BaseModel):
    """Product-wise supply, demand, allocation, and cost metrics."""

    product_code: str
    product_name: str
    unit: str
    total_supply: float
    total_demand: float
    total_allocated: float
    total_unmet: float
    fulfillment_pct: float
    transport_cost: float


class HospitalSummaryItem(BaseModel):
    """Hospital-wise demand fulfillment and allocation cost metrics."""

    hospital_code: str
    hospital_name: str
    priority_level: str
    total_demand: float
    total_allocated: float
    total_unmet: float
    fulfillment_pct: float
    transport_cost: float


class StageResultItem(BaseModel):
    """Per-stage solver status and optimal objective for lexicographic / LP runs."""

    stage: int
    name: str
    priority_tier: str
    objective_metric: str
    objective_value: float | None = None
    tier_demand: float | None = None
    solver_status: str
    execution_time_ms: float
    skipped: bool = False


class OptimizationResultResponse(BaseModel):
    """Structured response returned by optimization run and detail endpoints."""

    id: int | None = None
    run_code: str
    executed_at: datetime | None = None
    model_type: str
    solver_name: str = "PuLP CBC (COIN-OR Branch and Cut)"
    solver_status: str
    is_planned_allocation: bool = True
    total_cost: float
    total_demand: float = 0.0
    total_allocated: float
    total_unmet_demand: float
    fulfillment_percentage: float = 0.0
    tier_unmet_fractions: dict[str, float] = Field(default_factory=dict)
    priority_summary: list[PriorityTierSummary] = Field(default_factory=list)
    warehouse_utilization: list[WarehouseUtilizationItem] = Field(default_factory=list)
    product_summary: list[ProductSummaryItem] = Field(default_factory=list)
    hospital_summary: list[HospitalSummaryItem] = Field(default_factory=list)
    stage_results: list[StageResultItem] = Field(default_factory=list)
    execution_time_ms: float
    allocations: list[AllocationItem] = Field(default_factory=list)
    unmet_demands: list[UnmetDemandItem] = Field(default_factory=list)
    formulation_summary: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None


class OptimizationComparisonResponse(BaseModel):
    """Side-by-side comparison of Transportation LP vs. Lexicographic Priority LP."""

    transportation: OptimizationResultResponse
    lexicographic_priority: OptimizationResultResponse
    comparison_metrics: dict[str, Any]


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
