"""Inventory domain service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import Inventory
from app.schemas.inventory import InventoryCreate, InventoryUpdate


def list_inventory(
    db: Session,
    warehouse_id: int | None = None,
    product_id: int | None = None,
) -> list[Inventory]:
    """Return inventory records optionally filtered by warehouse or product."""
    stmt = select(Inventory).order_by(Inventory.inventory_code)
    if warehouse_id is not None:
        stmt = stmt.where(Inventory.warehouse_id == warehouse_id)
    if product_id is not None:
        stmt = stmt.where(Inventory.product_id == product_id)
    return list(db.scalars(stmt).all())


def get_inventory_item(db: Session, inventory_id: int) -> Inventory | None:
    """Fetch an inventory record by primary key."""
    return db.get(Inventory, inventory_id)


def create_inventory_item(db: Session, payload: InventoryCreate) -> Inventory:
    """Create a new warehouse-product inventory record."""
    item = Inventory(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_inventory_item(
    db: Session, item: Inventory, payload: InventoryUpdate
) -> Inventory:
    """Update stock levels for an existing inventory record."""
    updates = payload.model_dump(exclude_unset=True)
    new_available = updates.get("quantity_available", item.quantity_available)
    new_reserved = updates.get("quantity_reserved", item.quantity_reserved)
    if new_reserved > new_available:
        raise ValueError("quantity_reserved cannot exceed quantity_available")

    for field, value in updates.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_inventory_item(db: Session, item: Inventory) -> None:
    """Delete an inventory record."""
    db.delete(item)
    db.commit()
