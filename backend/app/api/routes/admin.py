"""
Admin Management API (/api/admin) — Strictly restricted to ADMIN role.

Covers:
- User CRUD, registration approval/rejection, activation/deactivation (protecting last active admin)
- Admin-initiated password recovery
- Hospital emergency order approval / rejection
- Fleet Vehicle CRUD & Delivery driver assignment
- Append-only Audit Log inspection
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_admin
from app.api.routes.auth import serialize_user
from app.core.config import get_settings
from app.core.security import generate_secure_token, hash_password, hash_token
from app.database.connection import get_db
from app.models.demand import Demand
from app.models.dispatch import VehicleAssignment
from app.models.hospital import Hospital
from app.models.platform import AuditLog
from app.models.user import PasswordResetToken, RefreshToken, User
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse
from app.schemas.auth import (
    AdminRejectRequest,
    AdminStatusToggleRequest,
    AdminUserCreateRequest,
    AdminUserUpdateRequest,
    AuditLogResponse,
    UserSummaryResponse,
)
from app.services import audit_service, email_service, onboarding_service

router = APIRouter(prefix="/api/admin", tags=["Admin Management"])


class AdminVehicleCreate(BaseModel):
    vehicle_code: str = Field(..., min_length=2, max_length=32)
    warehouse_id: int = Field(..., gt=0)
    vehicle_type: str = Field(default="medical_van", min_length=2, max_length=64)
    capacity_kg: float = Field(..., gt=0)
    status: Literal["available", "maintenance", "unavailable"] = "available"
    assigned_driver_user_id: int | None = Field(default=None, gt=0)


class AdminVehicleUpdate(BaseModel):
    warehouse_id: int | None = Field(default=None, gt=0)
    vehicle_type: str | None = Field(default=None, min_length=2, max_length=64)
    capacity_kg: float | None = Field(default=None, gt=0)
    status: Literal["available", "maintenance", "unavailable"] | None = None
    assigned_driver_user_id: int | None = None


def _count_other_active_admins(db: Session, exclude_user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(User.id)).where(
                User.role == "admin",
                User.is_active.is_(True),
                User.is_approved.is_(True),
                User.approval_status == "approved",
                User.id != exclude_user_id,
            )
        )
        or 0
    )


def _validate_org_links(
    db: Session,
    role: str,
    hosp_id: int | None,
    wh_id: int | None,
) -> tuple[int | None, int | None]:
    if role == "hospital":
        if not hosp_id or not db.get(Hospital, hosp_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hospital users must be linked to a valid hospital.",
            )
        return hosp_id, None
    if role == "warehouse":
        if not wh_id or not db.get(Warehouse, wh_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Warehouse users must be linked to a valid warehouse.",
            )
        return None, wh_id
    return None, None


# =============================================================================
# USER MANAGEMENT
# =============================================================================


@router.get("/users", response_model=list[UserSummaryResponse])
def list_users(
    role: str | None = Query(default=None),
    approval_status: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[UserSummaryResponse]:
    """List all platform users with optional role/approval/status/search filters."""
    stmt = select(User).order_by(User.created_at.desc(), User.id.desc())
    if role:
        stmt = stmt.where(User.role == role.lower())
    if approval_status:
        stmt = stmt.where(User.approval_status == approval_status.lower())
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    users = list(db.scalars(stmt).all())
    if search:
        q = search.strip().lower()
        users = [u for u in users if q in u.full_name.lower() or q in u.email.lower()]
    return [serialize_user(db, u) for u in users]


@router.post("/users", response_model=UserSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminUserCreateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserSummaryResponse:
    """Admin-only user creation supporting all roles including ADMIN."""
    normalized_email = str(payload.email).strip().lower()
    if db.scalar(select(User).where(User.email == normalized_email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists.",
        )

    hosp_id, wh_id = _validate_org_links(
        db, payload.role, payload.associated_hospital_id, payload.associated_warehouse_id
    )
    user = User(
        full_name=payload.full_name.strip(),
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        phone_number=payload.phone_number.strip() if payload.phone_number else None,
        is_active=payload.is_active,
        is_verified=payload.is_verified,
        is_approved=payload.is_approved,
        approval_status="approved" if payload.is_approved else "pending",
        associated_hospital_id=hosp_id,
        associated_warehouse_id=wh_id,
    )
    db.add(user)
    db.flush()
    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.user_created",
        target_entity="user",
        target_id=user.id,
        metadata={"role": user.role, "email": user.email},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return serialize_user(db, user)


@router.patch("/users/{user_id}", response_model=UserSummaryResponse)
def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserSummaryResponse:
    """Update permitted user fields, role, or organization association (protects last active admin)."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    new_role = payload.role if payload.role is not None else user.role
    new_active = payload.is_active if payload.is_active is not None else user.is_active

    if user.role == "admin" and (new_role != "admin" or not new_active):
        if _count_other_active_admins(db, user.id) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote or deactivate the last active administrator.",
            )

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.phone_number is not None:
        user.phone_number = payload.phone_number.strip() or None
    if payload.is_verified is not None:
        user.is_verified = payload.is_verified

    raw_hosp = (
        payload.associated_hospital_id
        if "associated_hospital_id" in payload.model_fields_set
        else user.associated_hospital_id
    )
    raw_wh = (
        payload.associated_warehouse_id
        if "associated_warehouse_id" in payload.model_fields_set
        else user.associated_warehouse_id
    )
    hosp_id, wh_id = _validate_org_links(db, new_role, raw_hosp, raw_wh)
    user.role = new_role
    user.associated_hospital_id = hosp_id
    user.associated_warehouse_id = wh_id
    user.is_active = new_active

    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.user_updated",
        target_entity="user",
        target_id=user.id,
        metadata={"role": user.role, "is_active": user.is_active},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return serialize_user(db, user)


@router.patch("/users/{user_id}/approve", response_model=UserSummaryResponse)
def approve_user_registration(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserSummaryResponse:
    """Approve a pending user registration so the user can sign into their role portal."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    user.is_approved = True
    user.is_active = True
    user.approval_status = "approved"
    user.rejection_reason = None

    # Automatically activate any newly onboarded Hospital, Warehouse, or Vehicle + generate corridors
    onboarding_info = onboarding_service.activate_onboarded_entities_for_user(db, user)

    audit_service.create_notification(
        db,
        user_id=user.id,
        title="Account Approved",
        message=f"Your MEDILOGIX {user.role.upper()} account has been approved by an administrator.",
        category="account",
        entity_type="user",
        entity_id=user.id,
    )
    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.user_approved",
        target_entity="user",
        target_id=user.id,
        metadata={"email": user.email, "role": user.role, **onboarding_info},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return serialize_user(db, user)


@router.patch("/users/{user_id}/reject", response_model=UserSummaryResponse)
def reject_user_registration(
    user_id: int,
    payload: AdminRejectRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserSummaryResponse:
    """Reject a pending registration with a clear reason."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if user.role == "admin" and _count_other_active_admins(db, user.id) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject the last active administrator.",
        )

    user.is_approved = False
    user.approval_status = "rejected"
    user.rejection_reason = payload.reason.strip()
    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.user_rejected",
        target_entity="user",
        target_id=user.id,
        metadata={"email": user.email, "reason": user.rejection_reason},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return serialize_user(db, user)


@router.patch("/users/{user_id}/status", response_model=UserSummaryResponse)
def toggle_user_active_status(
    user_id: int,
    payload: AdminStatusToggleRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> UserSummaryResponse:
    """Activate or deactivate an account without destroying historical records."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    if not payload.is_active and user.role == "admin" and _count_other_active_admins(db, user.id) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate the last active administrator.",
        )

    user.is_active = payload.is_active
    if not payload.is_active:
        now = datetime.now(timezone.utc)
        for tok in db.scalars(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
            )
        ).all():
            tok.revoked_at = now

    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.user_status_changed",
        target_entity="user",
        target_id=user.id,
        metadata={"is_active": user.is_active},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(user)
    return serialize_user(db, user)


@router.post("/users/{user_id}/initiate-recovery")
def initiate_user_password_recovery(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Admin-initiated single-use password reset link for an account."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    settings = get_settings()
    raw_token = generate_secure_token(32)
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.password_reset_expire_minutes),
        )
    )
    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.password_recovery_initiated",
        target_entity="user",
        target_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()

    email_info = email_service.send_password_reset_email(user.email, user.full_name, raw_token)
    out: dict[str, Any] = {
        "message": f"Password recovery initiated for {user.email}.",
        "email_delivery_mode": email_info["delivery_mode"],
    }
    if "dev_reset_url" in email_info:
        out["dev_reset_url"] = email_info["dev_reset_url"]
    return out


# =============================================================================
# ORDER / DEMAND APPROVAL WORKFLOW
# =============================================================================


@router.post("/orders/{demand_id}/approve")
def approve_hospital_order(
    demand_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Approve a pending hospital order so it becomes eligible for LP optimization."""
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order/Demand not found.")
    if demand.approval_status == "approved" and demand.status == "open":
        return {"message": "Order is already approved.", "id": demand.id, "status": demand.status}
    if demand.status in {"fulfilled", "cancelled"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve order in terminal status '{demand.status}'.",
        )

    demand.approval_status = "approved"
    demand.status = "open"
    demand.rejection_reason = None
    demand.reviewed_by_user_id = admin.id
    demand.reviewed_at = datetime.now(timezone.utc)

    audit_service.notify_users_by_role(
        db,
        role="hospital",
        hospital_id=demand.hospital_id,
        title=f"Order Approved — {demand.demand_code}",
        message=(
            f"Your {demand.priority_level.upper()} order {demand.demand_code} "
            f"({demand.quantity_requested} units) was approved and is now eligible for optimization."
        ),
        category="order",
        entity_type="demand",
        entity_id=demand.id,
    )
    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.order_approved",
        target_entity="demand",
        target_id=demand.id,
        metadata={"demand_code": demand.demand_code, "hospital_id": demand.hospital_id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {
        "id": demand.id,
        "demand_code": demand.demand_code,
        "status": demand.status,
        "approval_status": demand.approval_status,
        "message": f"Order {demand.demand_code} approved for optimization.",
    }


@router.post("/orders/{demand_id}/reject")
def reject_hospital_order(
    demand_id: int,
    payload: AdminRejectRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Reject a pending hospital order with reason (keeps it out of optimization)."""
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order/Demand not found.")
    if demand.status in {"fulfilled"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reject a fulfilled order.",
        )

    demand.approval_status = "rejected"
    demand.status = "rejected"
    demand.rejection_reason = payload.reason.strip()
    demand.reviewed_by_user_id = admin.id
    demand.reviewed_at = datetime.now(timezone.utc)

    audit_service.notify_users_by_role(
        db,
        role="hospital",
        hospital_id=demand.hospital_id,
        title=f"Order Rejected — {demand.demand_code}",
        message=f"Order {demand.demand_code} was rejected. Reason: {demand.rejection_reason}",
        category="order",
        entity_type="demand",
        entity_id=demand.id,
    )
    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.order_rejected",
        target_entity="demand",
        target_id=demand.id,
        metadata={"demand_code": demand.demand_code, "reason": demand.rejection_reason},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {
        "id": demand.id,
        "demand_code": demand.demand_code,
        "status": demand.status,
        "approval_status": demand.approval_status,
        "rejection_reason": demand.rejection_reason,
    }


# =============================================================================
# FLEET VEHICLE CRUD & DRIVER ASSIGNMENT
# =============================================================================


@router.get("/vehicles")
def list_admin_vehicles(
    _admin: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    wh_map = {w.id: w for w in db.scalars(select(Warehouse)).all()}
    drv_map = {
        u.id: u for u in db.scalars(select(User).where(User.role == "delivery")).all()
    }
    vehicles = list(db.scalars(select(Vehicle).order_by(Vehicle.vehicle_code)).all())
    return [
        {
            "id": v.id,
            "vehicle_code": v.vehicle_code,
            "warehouse_id": v.warehouse_id,
            "warehouse_code": wh_map[v.warehouse_id].code if v.warehouse_id in wh_map else None,
            "warehouse_area": wh_map[v.warehouse_id].area if v.warehouse_id in wh_map else None,
            "vehicle_type": v.vehicle_type,
            "capacity_kg": v.capacity_kg,
            "status": v.status,
            "assigned_driver_user_id": v.assigned_driver_user_id,
            "assigned_driver_name": (
                drv_map[v.assigned_driver_user_id].full_name
                if v.assigned_driver_user_id in drv_map
                else None
            ),
            "assigned_driver_email": (
                drv_map[v.assigned_driver_user_id].email
                if v.assigned_driver_user_id in drv_map
                else None
            ),
        }
        for v in vehicles
    ]


@router.post("/vehicles", status_code=status.HTTP_201_CREATED)
def create_vehicle(
    payload: AdminVehicleCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not db.get(Warehouse, payload.warehouse_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found.")
    if db.scalar(select(Vehicle).where(Vehicle.vehicle_code == payload.vehicle_code)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Vehicle code '{payload.vehicle_code}' already exists.",
        )
    if payload.assigned_driver_user_id:
        drv = db.get(User, payload.assigned_driver_user_id)
        if not drv or drv.role != "delivery":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned driver must be an existing DELIVERY user.",
            )

    veh = Vehicle(**payload.model_dump())
    db.add(veh)
    db.flush()
    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.vehicle_created",
        target_entity="vehicle",
        target_id=veh.id,
        metadata={"vehicle_code": veh.vehicle_code, "warehouse_id": veh.warehouse_id},
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(veh)
    return {"id": veh.id, "vehicle_code": veh.vehicle_code, "status": veh.status}


@router.put("/vehicles/{vehicle_id}")
def update_vehicle(
    vehicle_id: int,
    payload: AdminVehicleUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    veh = db.get(Vehicle, vehicle_id)
    if not veh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found.")
    data = payload.model_dump(exclude_unset=True)
    if "warehouse_id" in data and not db.get(Warehouse, data["warehouse_id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found.")
    if "assigned_driver_user_id" in data and data["assigned_driver_user_id"] is not None:
        drv = db.get(User, data["assigned_driver_user_id"])
        if not drv or drv.role != "delivery":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Assigned driver must be a DELIVERY user.",
            )

    for k, v in data.items():
        setattr(veh, k, v)

    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.vehicle_updated",
        target_entity="vehicle",
        target_id=veh.id,
        metadata=data,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(veh)
    return {
        "id": veh.id,
        "vehicle_code": veh.vehicle_code,
        "status": veh.status,
        "assigned_driver_user_id": veh.assigned_driver_user_id,
    }


@router.patch("/assignments/{assignment_id}/driver")
def assign_driver_to_dispatch_assignment(
    assignment_id: int,
    driver_user_id: int = Query(..., gt=0),
    request: Request = None,  # type: ignore[assignment]
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Assign a specific DELIVERY user to a persisted VehicleAssignment."""
    va = db.get(VehicleAssignment, assignment_id)
    if not va:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    drv = db.get(User, driver_user_id)
    if not drv or drv.role != "delivery" or not drv.is_active or not drv.is_approved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver must be an active, approved DELIVERY user.",
        )

    va.assigned_driver_user_id = drv.id
    audit_service.create_notification(
        db,
        user_id=drv.id,
        title="New Delivery Route Assigned",
        message=f"You have been assigned Vehicle Assignment #{va.id} (Wave #{va.trip_number}).",
        category="dispatch",
        entity_type="vehicle_assignment",
        entity_id=va.id,
    )
    audit_service.log_audit_event(
        db,
        actor=admin,
        action="admin.assignment_driver_assigned",
        target_entity="vehicle_assignment",
        target_id=va.id,
        metadata={"driver_user_id": drv.id, "driver_email": drv.email},
        ip_address=get_client_ip(request) if request else None,
    )
    db.commit()
    return {"id": va.id, "assigned_driver_user_id": drv.id, "driver_name": drv.full_name}


# =============================================================================
# AUDIT LOGS (APPEND-ONLY READ)
# =============================================================================


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    action: str | None = Query(default=None),
    target_entity: str | None = Query(default=None),
    actor_role: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AuditLogResponse]:
    """Retrieve append-only system & security audit logs ordered most recent first."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action.strip()}%"))
    if target_entity:
        stmt = stmt.where(AuditLog.target_entity == target_entity.strip())
    if actor_role:
        stmt = stmt.where(AuditLog.actor_role == actor_role.strip().lower())
    return list(db.scalars(stmt.limit(limit)).all())
