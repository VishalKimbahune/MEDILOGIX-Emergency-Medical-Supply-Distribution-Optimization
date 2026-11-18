"""Pydantic v2 schemas for Warehouse endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class WarehouseBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=32, examples=["WH-01"])
    name: str = Field(..., min_length=2, max_length=160)
    area: str = Field(..., min_length=2, max_length=80)
    city: str = Field(default="Pune", max_length=80)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    storage_capacity_units: int = Field(..., gt=0)
    status: Literal["active", "inactive", "maintenance"] = "active"
    is_synthetic_hub: bool = True


class WarehouseCreate(WarehouseBase):
    """Schema for creating a warehouse."""


class WarehouseUpdate(BaseModel):
    """Schema for partial or full warehouse updates."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    area: str | None = Field(default=None, min_length=2, max_length=80)
    city: str | None = Field(default=None, max_length=80)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    storage_capacity_units: int | None = Field(default=None, gt=0)
    status: Literal["active", "inactive", "maintenance"] | None = None


class WarehouseResponse(WarehouseBase):
    """Schema returned for warehouse queries."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
