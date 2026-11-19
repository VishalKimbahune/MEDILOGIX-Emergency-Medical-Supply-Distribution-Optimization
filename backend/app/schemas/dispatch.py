"""Pydantic v2 schemas for Phase 4A/4B Vehicle Routing & Dispatch Management."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DispatchStatus = Literal[
    "planned",
    "dispatched",
    "in_transit",
    "delivered",
    "partially_delivered",
    "cancelled",
]

RoutingObjective = Literal["min_distance", "min_time"]
RoutingSource = Literal["osm", "synthetic_fallback"]


class VehicleResponse(BaseModel):
    """Fleet vehicle stationed at a distribution warehouse."""

    id: int
    vehicle_code: str
    warehouse_id: int
    warehouse_code: str | None = None
    warehouse_area: str | None = None
    vehicle_type: str
    capacity_kg: float
    status: str
    assigned_driver_user_id: int | None = None
    assigned_driver_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DispatchPlanCreateRequest(BaseModel):
    """Request to generate & persist vehicle routes from a completed OptimizationRun."""

    optimization_run_id: int = Field(..., gt=0)
    allow_multi_trip: bool = True
    max_trips_per_vehicle: int = Field(default=3, ge=1, le=10)
    allow_split_deliveries: bool = True
    routing_objective: RoutingObjective = "min_distance"
    closed_route_codes: list[str] = Field(default_factory=list)
    closed_way_ids: list[int] = Field(default_factory=list)
    disabled_vehicle_codes: list[str] = Field(default_factory=list)
    search_time_limit_sec: int = Field(default=2, ge=1, le=30)
    notes: str | None = Field(default=None, max_length=500)


class DispatchStatusUpdateRequest(BaseModel):
    """Request to transition a dispatch plan's lifecycle status."""

    status: DispatchStatus
    notes: str | None = Field(default=None, max_length=500)


class ShipmentLineDeliveryUpdate(BaseModel):
    """Optional delivered quantity update for a single product line at a stop."""

    shipment_line_id: int = Field(..., gt=0)
    quantity_delivered: float = Field(..., ge=0.0)


class StopStatusUpdateRequest(BaseModel):
    """Request to transition an individual hospital delivery stop status."""

    status: DispatchStatus
    notes: str | None = Field(default=None, max_length=255)
    shipment_updates: list[ShipmentLineDeliveryUpdate] = Field(default_factory=list)


class ShipmentLineResponse(BaseModel):
    """Product-level shipment record at a delivery stop."""

    id: int
    product_id: int
    product_code: str
    product_name: str
    unit: str
    quantity_planned: float
    quantity_delivered: float
    unit_weight_kg: float
    total_weight_kg: float


class DeliveryStopResponse(BaseModel):
    """Ordered hospital stop inside a vehicle tour."""

    id: int
    hospital_id: int
    hospital_code: str
    hospital_name: str
    hospital_area: str
    priority_level: str
    latitude: float
    longitude: float
    stop_sequence: int
    status: DispatchStatus
    leg_distance_km: float
    cumulative_distance_km: float
    estimated_arrival_min: float
    stop_weight_kg: float
    notes: str | None = None
    shipment_lines: list[ShipmentLineResponse] = Field(default_factory=list)


class VehicleAssignmentResponse(BaseModel):
    """Assigned vehicle tour originating from and returning to its warehouse depot."""

    id: int
    vehicle_id: int
    vehicle_code: str
    vehicle_type: str
    warehouse_id: int
    warehouse_code: str
    warehouse_name: str
    trip_number: int
    status: DispatchStatus
    assigned_driver_user_id: int | None = None
    assigned_driver_name: str | None = None
    preparation_status: str | None = None
    total_load_kg: float
    capacity_kg: float
    utilization_pct: float
    route_distance_km: float
    estimated_duration_min: float
    routing_source: str = "synthetic_fallback"
    routing_objective: str = "min_distance"
    fallback_used: bool = False
    geometry_point_count: int = 0
    stop_count: int = 0
    route_coordinates: list[dict[str, Any]] = Field(default_factory=list)
    route_geometry: list[list[float]] = Field(default_factory=list)
    osm_way_ids: list[int] = Field(default_factory=list)
    road_names: list[str] = Field(default_factory=list)
    delivery_stops: list[DeliveryStopResponse] = Field(default_factory=list)


class DispatchPlanSummaryResponse(BaseModel):
    """Summary schema for dispatch plan history listing."""

    id: int
    plan_code: str
    optimization_run_id: int
    optimization_run_code: str | None = None
    status: DispatchStatus
    solver_status: str
    routing_source: str = "synthetic_fallback"
    routing_objective: str = "min_distance"
    total_vehicles_used: int
    total_routes: int
    total_stops: int
    total_distance_km: float
    estimated_duration_min: float
    total_weight_kg: float
    allow_multi_trip: bool
    allow_split_deliveries: bool
    created_at: datetime


class DispatchPlanDetailResponse(DispatchPlanSummaryResponse):
    """Full dispatch plan response including all vehicle assignments, stops, and shipment lines."""

    notes: str | None = None
    infeasibility_reasons: list[str] = Field(default_factory=list)
    depot_summaries: list[dict[str, Any]] = Field(default_factory=list)
    closed_route_codes: list[str] = Field(default_factory=list)
    closed_way_ids: list[int] = Field(default_factory=list)
    closed_osm_ways: list[dict[str, Any]] = Field(default_factory=list)
    unreachable_hospitals: list[str] = Field(default_factory=list)
    unreachable_connections: list[dict[str, Any]] = Field(default_factory=list)
    fallback_used: bool = False
    fallback_warning: str | None = None
    attribution: str = "© OpenStreetMap contributors (ODbL 1.0)"
    travel_time_disclaimer: str = (
        "Estimated travel time based on OpenStreetMap road classification and assumed speeds; "
        "not live traffic or guaranteed arrival times."
    )
    vehicle_assignments: list[VehicleAssignmentResponse] = Field(default_factory=list)
