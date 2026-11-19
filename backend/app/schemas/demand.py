"""Pydantic v2 schemas for Hospital Demand endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PriorityLevel = Literal["critical", "high", "normal"]
DemandStatus = Literal[
    "pending_approval",
    "open",
    "partially_fulfilled",
    "fulfilled",
    "rejected",
    "cancelled",
]


class DemandBase(BaseModel):
    demand_code: str = Field(..., min_length=2, max_length=32, examples=["DEM-001"])
    hospital_id: int = Field(..., gt=0)
    product_id: int = Field(..., gt=0)
    quantity_requested: int = Field(..., gt=0)
    priority_level: PriorityLevel = "normal"
    status: DemandStatus = "open"
    data_note: str | None = Field(default=None, max_length=200)


class DemandCreate(DemandBase):
    """Schema for creating a hospital demand request."""


class DemandUpdate(BaseModel):
    """Schema for updating demand quantity, priority, or status."""

    quantity_requested: int | None = Field(default=None, gt=0)
    priority_level: PriorityLevel | None = None
    status: DemandStatus | None = None
    data_note: str | None = Field(default=None, max_length=200)


class DemandResponse(DemandBase):
    """Schema returned for demand queries."""

    id: int
    order_group_code: str | None = None
    approval_status: str | None = None
    emergency_reason: str | None = None
    required_by: datetime | None = None
    rejection_reason: str | None = None
    submitted_by_user_id: int | None = None
    reviewed_by_user_id: int | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
