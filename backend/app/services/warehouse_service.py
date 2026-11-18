"""Warehouse domain service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

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
