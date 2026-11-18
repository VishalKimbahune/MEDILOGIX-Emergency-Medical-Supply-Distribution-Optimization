"""Hospital domain service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.hospital import Hospital
from app.schemas.hospital import HospitalCreate, HospitalUpdate


def list_hospitals(db: Session, priority_level: str | None = None) -> list[Hospital]:
    """Return all hospitals, optionally filtered by priority_level."""
    stmt = select(Hospital).order_by(Hospital.code)
    if priority_level:
        stmt = stmt.where(Hospital.priority_level == priority_level)
    return list(db.scalars(stmt).all())


def get_hospital(db: Session, hospital_id: int) -> Hospital | None:
    """Fetch a single hospital by primary key."""
    return db.get(Hospital, hospital_id)


def get_hospital_by_code(db: Session, code: str) -> Hospital | None:
    """Fetch a single hospital by unique code."""
    return db.scalar(select(Hospital).where(Hospital.code == code))


def create_hospital(db: Session, payload: HospitalCreate) -> Hospital:
    """Create and persist a new hospital."""
    hospital = Hospital(**payload.model_dump())
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return hospital


def update_hospital(db: Session, hospital: Hospital, payload: HospitalUpdate) -> Hospital:
    """Update an existing hospital record."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(hospital, field, value)
    db.commit()
    db.refresh(hospital)
    return hospital


def delete_hospital(db: Session, hospital: Hospital) -> None:
    """Delete a hospital record."""
    db.delete(hospital)
    db.commit()
