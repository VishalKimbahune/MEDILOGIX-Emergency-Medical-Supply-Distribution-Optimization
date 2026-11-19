"""Hospital API routes (/api/hospitals)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.connection import get_db
from app.schemas.hospital import HospitalCreate, HospitalResponse, HospitalUpdate
from app.services import hospital_service

router = APIRouter(
    prefix="/api/hospitals",
    tags=["Hospitals"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[HospitalResponse])
def list_hospitals(
    priority_level: str | None = Query(default=None, description="Filter by critical|high|normal"),
    area: str | None = Query(default=None, description="Filter by locality name"),
    db: Session = Depends(get_db),
) -> list[HospitalResponse]:
    """List all synthetic hospital profiles."""
    return hospital_service.list_hospitals(db, priority_level=priority_level, area=area)


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
    """Remove a hospital node only when no dependent records reference it."""
    hospital = hospital_service.get_hospital(db, hospital_id)
    if not hospital:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hospital not found")

    deps = hospital_service.get_hospital_dependency_counts(db, hospital_id)
    if deps:
        summary = ", ".join(f"{count} {name}" for name, count in deps.items())
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot delete hospital '{hospital.code}' because it has dependent records "
                f"({summary}). Remove or reassign dependent records first."
            ),
        )

    try:
        hospital_service.delete_hospital(db, hospital)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot delete hospital '{hospital.code}' due to existing foreign-key references.",
        ) from exc
