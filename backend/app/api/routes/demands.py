"""Hospital Demand API routes (/api/demands)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.hospital import Hospital
from app.models.product import Product
from app.schemas.demand import DemandCreate, DemandResponse, DemandUpdate
from app.services import demand_service

router = APIRouter(prefix="/api/demands", tags=["Demands"])


@router.get("", response_model=list[DemandResponse])
def list_demands(
    hospital_id: int | None = Query(default=None),
    product_id: int | None = Query(default=None),
    priority_level: str | None = Query(default=None),
    demand_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[DemandResponse]:
    """List hospital supply demand requests."""
    return demand_service.list_demands(
        db,
        hospital_id=hospital_id,
        product_id=product_id,
        priority_level=priority_level,
        status=demand_status,
    )


@router.get("/{demand_id}", response_model=DemandResponse)
def get_demand(demand_id: int, db: Session = Depends(get_db)) -> DemandResponse:
    """Retrieve a single demand request."""
    demand = demand_service.get_demand(db, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand request not found")
    return demand


@router.post("", response_model=DemandResponse, status_code=status.HTTP_201_CREATED)
def create_demand(payload: DemandCreate, db: Session = Depends(get_db)) -> DemandResponse:
    """Create a new hospital supply demand request with foreign-key validation."""
    if not db.get(Hospital, payload.hospital_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Hospital with id {payload.hospital_id} does not exist",
        )
    if not db.get(Product, payload.product_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id {payload.product_id} does not exist",
        )
    try:
        return demand_service.create_demand(db, payload)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Demand request with code '{payload.demand_code}' already exists",
        ) from exc


@router.put("/{demand_id}", response_model=DemandResponse)
def update_demand(
    demand_id: int, payload: DemandUpdate, db: Session = Depends(get_db)
) -> DemandResponse:
    """Update a demand request."""
    demand = demand_service.get_demand(db, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand request not found")
    return demand_service.update_demand(db, demand, payload)


@router.delete("/{demand_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_demand(demand_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a demand request."""
    demand = demand_service.get_demand(db, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Demand request not found")
    demand_service.delete_demand(db, demand)
