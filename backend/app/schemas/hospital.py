"""Pydantic v2 schemas for Hospital endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PriorityLevel = Literal["critical", "high", "normal"]


class HospitalBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=32, examples=["HOSP-01"])
    name: str = Field(..., min_length=2, max_length=160)
    area: str = Field(..., min_length=2, max_length=80)
    city: str = Field(default="Pune", max_length=80)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    priority_level: PriorityLevel = "normal"
    bed_capacity: int = Field(..., gt=0)
    status: Literal["active", "inactive"] = "active"
    is_synthetic_profile: bool = True


class HospitalCreate(HospitalBase):
    """Schema for registering a hospital node."""


class HospitalUpdate(BaseModel):
    """Schema for updating hospital attributes or emergency priority."""

    name: str | None = Field(default=None, min_length=2, max_length=160)
    area: str | None = Field(default=None, min_length=2, max_length=80)
    city: str | None = Field(default=None, max_length=80)
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    priority_level: PriorityLevel | None = None
    bed_capacity: int | None = Field(default=None, gt=0)
    status: Literal["active", "inactive"] | None = None


class HospitalResponse(HospitalBase):
    """Schema returned for hospital queries."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
