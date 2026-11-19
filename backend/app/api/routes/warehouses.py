"""Warehouse API routes (/api/warehouses)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.connection import get_db
from app.schemas.warehouse import WarehouseCreate, WarehouseResponse, WarehouseUpdate
from app.services import warehouse_service

router = APIRouter(
    prefix="/api/warehouses",
    tags=["Warehouses"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[WarehouseResponse])
def list_warehouses(db: Session = Depends(get_db)) -> list[WarehouseResponse]:
    """List all simulation medical warehouses."""
    return warehouse_service.list_warehouses(db)


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(warehouse_id: int, db: Session = Depends(get_db)) -> WarehouseResponse:
    """Retrieve a warehouse by ID."""
    warehouse = warehouse_service.get_warehouse(db, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    return warehouse


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    payload: WarehouseCreate, db: Session = Depends(get_db)
) -> WarehouseResponse:
    """Create a new warehouse."""
    if warehouse_service.get_warehouse_by_code(db, payload.code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Warehouse with code '{payload.code}' already exists",
        )
    return warehouse_service.create_warehouse(db, payload)


@router.put("/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(
    warehouse_id: int, payload: WarehouseUpdate, db: Session = Depends(get_db)
) -> WarehouseResponse:
    """Update an existing warehouse."""
    warehouse = warehouse_service.get_warehouse(db, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    return warehouse_service.update_warehouse(db, warehouse, payload)


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_warehouse(warehouse_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a warehouse only when no dependent operational records reference it."""
    warehouse = warehouse_service.get_warehouse(db, warehouse_id)
    if not warehouse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")

    deps = warehouse_service.get_warehouse_dependency_counts(db, warehouse_id)
    if deps:
        summary = ", ".join(f"{count} {name}" for name, count in deps.items())
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete warehouse '{warehouse.code}' because it has dependent records "
                f"({summary}). Remove or reassign dependent records first."
            ),
        )

    try:
        warehouse_service.delete_warehouse(db, warehouse)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete warehouse '{warehouse.code}' due to existing foreign-key references.",
        ) from exc
