"""Hospital API routes (/api/hospitals)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.hospital import HospitalCreate, HospitalResponse, HospitalUpdate
from app.services import hospital_service

router = APIRouter(prefix="/api/hospitals", tags=["Hospitals"])


@router.get("", response_model=list[HospitalResponse])
def list_hospitals(
    priority_level: str | None = Query(default=None, description="Filter by critical|high|normal"),
    db: Session = Depends(get_db),
) -> list[HospitalResponse]:
    """List all synthetic hospital profiles."""
    return hospital_service.list_hospitals(db, priority_level=priority_level)


@router.get("/{hospital_id}", response_model=HospitalResponse)
def get_hospital(hospital_id: int, db: Session = Depends(get_db)) -> HospitalResponse:
    """Retrieve a single hospital by ID."""
    hospital = hospital_service.get_hospital(db, hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    return hospital


@router.post("", response_model=HospitalResponse, status_code=status.HTTP_201_CREATED)
def create_hospital(
    payload: HospitalCreate, db: Session = Depends(get_db)
) -> HospitalResponse:
    """Register a new hospital node."""
    if hospital_service.get_hospital_by_code(db, payload.code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Hospital with code '{payload.code}' already exists",
        )
    return hospital_service.create_hospital(db, payload)


@router.put("/{hospital_id}", response_model=HospitalResponse)
def update_hospital(
    hospital_id: int, payload: HospitalUpdate, db: Session = Depends(get_db)
) -> HospitalResponse:
    """Update hospital attributes or emergency priority."""
    hospital = hospital_service.get_hospital(db, hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    return hospital_service.update_hospital(db, hospital, payload)


@router.delete("/{hospital_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hospital(hospital_id: int, db: Session = Depends(get_db)) -> None:
    """Remove a hospital node."""
    hospital = hospital_service.get_hospital(db, hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")
    hospital_service.delete_hospital(db, hospital)
