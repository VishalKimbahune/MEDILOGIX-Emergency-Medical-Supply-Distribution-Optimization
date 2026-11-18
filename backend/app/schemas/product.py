"""Pydantic v2 schemas for Medical Product endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    code: str = Field(..., min_length=2, max_length=32, examples=["PROD-01"])
    name: str = Field(..., min_length=2, max_length=120)
    category: str = Field(..., min_length=2, max_length=80)
    unit: str = Field(..., min_length=1, max_length=32)
    unit_weight_kg: float = Field(..., gt=0)
    base_transport_cost_per_km: float = Field(..., ge=0)
    cold_chain_required: bool = False


class ProductCreate(ProductBase):
    """Schema for creating a medical product."""


class ProductUpdate(BaseModel):
    """Schema for updating a medical product."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    unit: str | None = Field(default=None, min_length=1, max_length=32)
    unit_weight_kg: float | None = Field(default=None, gt=0)
    base_transport_cost_per_km: float | None = Field(default=None, ge=0)
    cold_chain_required: bool | None = None


class ProductResponse(ProductBase):
    """Schema returned for product queries."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
