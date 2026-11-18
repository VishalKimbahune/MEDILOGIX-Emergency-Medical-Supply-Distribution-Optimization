"""Pydantic v2 schemas for Inventory endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InventoryBase(BaseModel):
    inventory_code: str = Field(..., min_length=2, max_length=32, examples=["INV-001"])
    warehouse_id: int = Field(..., gt=0)
    product_id: int = Field(..., gt=0)
    quantity_available: int = Field(..., ge=0)
    quantity_reserved: int = Field(default=0, ge=0)
    reorder_level: int = Field(default=20, ge=0)
    data_note: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_reserved_le_available(self) -> "InventoryBase":
        if self.quantity_reserved > self.quantity_available:
            raise ValueError("quantity_reserved cannot exceed quantity_available")
        return self


class InventoryCreate(InventoryBase):
    """Schema for creating an inventory record."""


class InventoryUpdate(BaseModel):
    """Schema for updating warehouse stock quantities."""

    quantity_available: int | None = Field(default=None, ge=0)
    quantity_reserved: int | None = Field(default=None, ge=0)
    reorder_level: int | None = Field(default=None, ge=0)
    data_note: str | None = Field(default=None, max_length=200)


class InventoryResponse(InventoryBase):
    """Schema returned for inventory queries."""

    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
