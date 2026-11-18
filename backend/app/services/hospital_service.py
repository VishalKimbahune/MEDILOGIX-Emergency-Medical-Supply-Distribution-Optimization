"""Hospital domain service."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.allocation import Allocation
from app.models.delivery import Delivery
from app.models.demand import Demand
from app.models.hospital import Hospital
from app.models.road import Road
from app.schemas.hospital import HospitalCreate, HospitalUpdate


def list_hospitals(
    db: Session,
    priority_level: str | None = None,
    area: str | None = None,
) -> list[Hospital]:
    """Return all hospitals, optionally filtered by priority_level or locality."""
    stmt = select(Hospital).order_by(Hospital.code)
    if priority_level:
        stmt = stmt.where(Hospital.priority_level == priority_level)
    if area:
        stmt = stmt.where(Hospital.area.ilike(f"%{area}%"))
    return list(db.scalars(stmt).all())


def get_hospital(db: Session, hospital_id: int) -> Hospital | None:
    """Fetch a single hospital by primary key."""
    return db.get(Hospital, hospital_id)


def get_hospital_by_code(db: Session, code: str) -> Hospital | None:
    """Fetch a single hospital by unique code."""
    return db.scalar(select(Hospital).where(Hospital.code == code))


def get_hospital_dependency_counts(db: Session, hospital_id: int) -> dict[str, int]:
    """Count dependent records referencing this hospital before allowing deletion."""
    counts = {
        "demands": db.scalar(
            select(func.count(Demand.id)).where(Demand.hospital_id == hospital_id)
        )
        or 0,
        "roads": db.scalar(
            select(func.count(Road.id)).where(Road.hospital_id == hospital_id)
        )
        or 0,
        "allocations": db.scalar(
            select(func.count(Allocation.id)).where(Allocation.hospital_id == hospital_id)
        )
        or 0,
        "deliveries": db.scalar(
            select(func.count(Delivery.id)).where(Delivery.hospital_id == hospital_id)
        )
        or 0,
    }
    return {k: int(v) for k, v in counts.items() if v > 0}


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
