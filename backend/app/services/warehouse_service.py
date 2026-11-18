"""Warehouse domain service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.delivery import Delivery
from app.models.inventory import Inventory
from app.models.road import Road
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate


def list_warehouses(db: Session) -> list[Warehouse]:
    """Return all warehouses ordered by code."""
    return list(db.scalars(select(Warehouse).order_by(Warehouse.code)).all())


def get_warehouse(db: Session, warehouse_id: int) -> Warehouse | None:
    """Fetch a single warehouse by primary key."""
    return db.get(Warehouse, warehouse_id)


def get_warehouse_by_code(db: Session, code: str) -> Warehouse | None:
    """Fetch a single warehouse by unique domain code."""
    return db.scalar(select(Warehouse).where(Warehouse.code == code))


def get_warehouse_dependency_counts(db: Session, warehouse_id: int) -> dict[str, int]:
    """Count dependent records referencing this warehouse before allowing deletion."""
    counts = {
        "inventory": db.scalar(
            select(func.count(Inventory.id)).where(Inventory.warehouse_id == warehouse_id)
        )
        or 0,
        "roads": db.scalar(
            select(func.count(Road.id)).where(Road.warehouse_id == warehouse_id)
        )
        or 0,
        "vehicles": db.scalar(
            select(func.count(Vehicle.id)).where(Vehicle.warehouse_id == warehouse_id)
        )
        or 0,
        "allocations": db.scalar(
            select(func.count(Allocation.id)).where(Allocation.warehouse_id == warehouse_id)
        )
        or 0,
        "deliveries": db.scalar(
            select(func.count(Delivery.id)).where(Delivery.warehouse_id == warehouse_id)
        )
        or 0,
    }
    return {k: int(v) for k, v in counts.items() if v > 0}


def create_warehouse(db: Session, payload: WarehouseCreate) -> Warehouse:
    """Create and persist a new warehouse."""
    warehouse = Warehouse(**payload.model_dump())
    db.add(warehouse)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def update_warehouse(
    db: Session, warehouse: Warehouse, payload: WarehouseUpdate
) -> Warehouse:
    """Update fields on an existing warehouse."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(warehouse, field, value)
    db.commit()
    db.refresh(warehouse)
    return warehouse


def delete_warehouse(db: Session, warehouse: Warehouse) -> None:
    """Remove a warehouse record."""
    db.delete(warehouse)
    db.commit()
