"""Inventory API routes (/api/inventory)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.inventory import InventoryCreate, InventoryResponse, InventoryUpdate
from app.services import inventory_service

router = APIRouter(prefix="/api/inventory", tags=["Inventory"])


@router.get("", response_model=list[InventoryResponse])
def list_inventory(
    warehouse_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[InventoryResponse]:
    """List warehouse-product inventory records."""
    return inventory_service.list_inventory(db, warehouse_id=warehouse_id, product_id=product_id)


@router.get("/{inventory_id}", response_model=InventoryResponse)
def get_inventory_item(inventory_id: int, db: Session = Depends(get_db)) -> InventoryResponse:
    """Retrieve a single inventory record."""
    item = inventory_service.get_inventory_item(db, inventory_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
    return item


@router.post("", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    payload: InventoryCreate, db: Session = Depends(get_db)
) -> InventoryResponse:
    """Create a new inventory record."""
    try:
        return inventory_service.create_inventory_item(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Duplicate inventory code or warehouse-product entry",
        ) from exc


@router.put("/{inventory_id}", response_model=InventoryResponse)
def update_inventory_item(
    inventory_id: int, payload: InventoryUpdate, db: Session = Depends(get_db)
) -> InventoryResponse:
    """Update stock levels for an inventory record."""
    item = inventory_service.get_inventory_item(db, inventory_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
    try:
        return inventory_service.update_inventory_item(db, item, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.delete("/{inventory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(inventory_id: int, db: Session = Depends(get_db)) -> None:
    """Delete an inventory record."""
    item = inventory_service.get_inventory_item(db, inventory_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
    inventory_service.delete_inventory_item(db, item)
