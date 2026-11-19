"""Hospital Demand domain service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.demand import Demand
from app.schemas.demand import DemandCreate, DemandUpdate


def list_demands(
    db: Session,
    hospital_id: int | None = None,
    product_id: int | None = None,
    priority_level: str | None = None,
    status: str | None = None,
) -> list[Demand]:
    """Return demand requests with optional filters, ordered by newest first."""
    stmt = select(Demand).order_by(Demand.id.desc())
    if hospital_id is not None:
        stmt = stmt.where(Demand.hospital_id == hospital_id)
    if product_id is not None:
        stmt = stmt.where(Demand.product_id == product_id)
    if priority_level:
        stmt = stmt.where(Demand.priority_level == priority_level)
    if status:
        stmt = stmt.where(Demand.status == status)
    return list(db.scalars(stmt).all())


def get_demand(db: Session, demand_id: int) -> Demand | None:
    """Fetch a single demand request by primary key."""
    return db.get(Demand, demand_id)


def create_demand(db: Session, payload: DemandCreate) -> Demand:
    """Create a new hospital demand request."""
    demand = Demand(**payload.model_dump())
    db.add(demand)
    db.commit()
    db.refresh(demand)
    return demand


def update_demand(db: Session, demand: Demand, payload: DemandUpdate) -> Demand:
    """Update an existing hospital demand request."""
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(demand, field, value)
    if payload.status == "open" and demand.approval_status == "pending_approval":
        demand.approval_status = "approved"
    elif payload.status == "rejected":
        demand.approval_status = "rejected"
    db.commit()
    db.refresh(demand)
    return demand


def delete_demand(db: Session, demand: Demand) -> None:
    """Delete a demand request."""
    db.delete(demand)
    db.commit()
