"""
Hospital Portal API (/api/hospital) — Strictly scoped to authenticated HOSPITAL user's own hospital.

Enforces strict cross-organization isolation at the API/DB level:
- Hospital users can NEVER view or modify another hospital's orders or profile.
- Hospital users can NEVER submit pre-approved orders (every order enters `pending_approval`).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_hospital_user
from app.database.connection import get_db
from app.models.allocation import Allocation
from app.models.demand import Demand
from app.models.dispatch import DeliveryStop, DispatchPlan, ShipmentLine, VehicleAssignment
from app.models.hospital import Hospital
from app.models.optimization_run import OptimizationRun
from app.models.product import Product
from app.models.user import User
from app.services import audit_service

router = APIRouter(prefix="/api/hospital", tags=["Hospital Portal"])


class HospitalOrderLineCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity_requested: int = Field(..., gt=0)


class HospitalOrderCreateRequest(BaseModel):
    priority_level: Literal["critical", "high", "normal"] = "normal"
    emergency_reason: str | None = Field(default=None, max_length=500)
    required_by: datetime | None = None
    data_note: str | None = Field(default=None, max_length=200)
    items: list[HospitalOrderLineCreate] = Field(..., min_length=1, max_length=20)


class HospitalProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    area: str | None = Field(default=None, min_length=2, max_length=80)
    bed_capacity: int | None = Field(default=None, gt=0)


def _get_bound_hospital(db: Session, user: User) -> Hospital:
    if not user.associated_hospital_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not associated with any hospital. Contact an administrator.",
        )
    hosp = db.get(Hospital, user.associated_hospital_id)
    if not hosp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Associated hospital record not found."
        )
    return hosp


def _build_order_tracking_view(
    db: Session,
    hospital: Hospital,
    demands: list[Demand],
) -> list[dict[str, Any]]:
    """Enrich hospital demands with latest LP allocation & dispatch delivery timeline."""
    prods = {p.id: p for p in db.scalars(select(Product)).all()}

    latest_run = db.scalar(
        select(OptimizationRun)
        .where(OptimizationRun.solver_status == "Optimal")
        .order_by(OptimizationRun.created_at.desc(), OptimizationRun.id.desc())
        .limit(1)
    )
    alloc_by_prod: dict[int, float] = defaultdict(float)
    unmet_by_prod: dict[int, float] = defaultdict(float)
    if latest_run:
        for a in db.scalars(
            select(Allocation).where(
                Allocation.optimization_run_id == latest_run.id,
                Allocation.hospital_id == hospital.id,
            )
        ).all():
            alloc_by_prod[a.product_id] += float(a.quantity_allocated)
            unmet_by_prod[a.product_id] += float(a.unmet_quantity)

    # Latest dispatch stop & shipment status per product for this hospital
    stops = list(
        db.scalars(
            select(DeliveryStop)
            .where(DeliveryStop.hospital_id == hospital.id)
            .order_by(DeliveryStop.created_at.desc(), DeliveryStop.id.desc())
        ).all()
    )
    va_map = {va.id: va for va in db.scalars(select(VehicleAssignment)).all()}
    plan_map = {p.id: p for p in db.scalars(select(DispatchPlan)).all()}

    dispatch_by_prod: dict[int, dict[str, Any]] = {}
    for stop in stops:
        va = va_map.get(stop.vehicle_assignment_id)
        plan = plan_map.get(va.dispatch_plan_id) if va else None
        for line in stop.shipment_lines:
            if line.product_id not in dispatch_by_prod:
                dispatch_by_prod[line.product_id] = {
                    "plan_code": plan.plan_code if plan else None,
                    "dispatch_status": plan.status if plan else None,
                    "stop_status": stop.status,
                    "quantity_planned": float(line.quantity_planned),
                    "quantity_delivered": float(line.quantity_delivered),
                    "estimated_arrival_min": stop.estimated_arrival_min,
                    "confirmed_at": stop.confirmed_at.isoformat() if stop.confirmed_at else None,
                }

    rows: list[dict[str, Any]] = []
    for d in demands:
        prod = prods.get(d.product_id)
        appr = d.approval_status or ("pending_approval" if d.status == "pending_approval" else "approved")
        disp = dispatch_by_prod.get(d.product_id) if appr == "approved" else None
        alloc_qty = round(alloc_by_prod.get(d.product_id, 0.0), 2) if appr == "approved" else 0.0
        unmet_qty = (
            round(max(0.0, float(d.quantity_requested) - alloc_qty), 2)
            if appr == "approved"
            else float(d.quantity_requested)
        )

        # Build honest visual tracking timeline
        stop_st = disp["stop_status"] if disp else None
        is_rejected = appr == "rejected" or d.status == "rejected"
        is_cancelled = d.status == "cancelled" or stop_st == "cancelled"
        is_approved = appr == "approved" and not is_rejected
        is_allocated = is_approved and alloc_qty > 0
        is_dispatched = stop_st in {"dispatched", "in_transit", "partially_delivered", "delivered"}
        is_in_transit = stop_st in {"in_transit", "partially_delivered", "delivered"}
        is_delivered = stop_st == "delivered" or d.status == "fulfilled"
        is_partial = stop_st == "partially_delivered" or d.status == "partially_fulfilled"

        timeline = [
            {"stage": "Submitted", "completed": True, "current": appr == "pending_approval"},
            {
                "stage": "Rejected" if is_rejected else "Approved",
                "completed": is_approved,
                "rejected": is_rejected,
                "current": is_approved and not is_allocated and not is_rejected,
            },
            {
                "stage": "Allocated",
                "completed": is_allocated,
                "current": is_allocated and not is_dispatched,
            },
            {
                "stage": "Dispatched",
                "completed": is_dispatched,
                "current": stop_st == "dispatched",
            },
            {
                "stage": "In Transit",
                "completed": is_in_transit,
                "current": stop_st == "in_transit",
            },
            {
                "stage": "Partially Delivered" if is_partial and not is_delivered else "Delivered",
                "completed": is_delivered,
                "partial": is_partial and not is_delivered,
                "cancelled": is_cancelled,
                "current": is_delivered or is_partial or is_cancelled,
            },
        ]

        rows.append(
            {
                "id": d.id,
                "demand_code": d.demand_code,
                "order_group_code": d.order_group_code,
                "hospital_id": d.hospital_id,
                "hospital_code": hospital.code,
                "product_id": d.product_id,
                "product_code": prod.code if prod else f"PROD-{d.product_id}",
                "product_name": prod.name if prod else f"Product #{d.product_id}",
                "unit": prod.unit if prod else "units",
                "quantity_requested": d.quantity_requested,
                "priority_level": d.priority_level,
                "status": d.status,
                "approval_status": appr,
                "emergency_reason": d.emergency_reason,
                "required_by": d.required_by.isoformat() if d.required_by else None,
                "rejection_reason": d.rejection_reason,
                "data_note": d.data_note,
                "allocated_quantity": alloc_qty,
                "unmet_quantity": unmet_qty,
                "dispatch_plan_code": disp["plan_code"] if disp else None,
                "dispatch_status": disp["dispatch_status"] if disp else None,
                "delivery_status": stop_st,
                "delivered_quantity": disp["quantity_delivered"] if disp else 0.0,
                "timeline": timeline,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            }
        )
    return rows


@router.get("/dashboard")
def hospital_dashboard(
    user: User = Depends(require_hospital_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Hospital-scoped operational dashboard KPIs and recent orders."""
    hospital = _get_bound_hospital(db, user)
    demands = list(
        db.scalars(
            select(Demand)
            .where(Demand.hospital_id == hospital.id)
            .order_by(Demand.created_at.desc(), Demand.id.desc())
        ).all()
    )
    enriched = _build_order_tracking_view(db, hospital, demands)

    return {
        "hospital": {
            "id": hospital.id,
            "code": hospital.code,
            "name": hospital.name,
            "area": hospital.area,
            "city": hospital.city,
            "priority_level": hospital.priority_level,
            "bed_capacity": hospital.bed_capacity,
            "status": hospital.status,
        },
        "kpis": {
            "total_orders": len(enriched),
            "pending_approval": sum(1 for o in enriched if o["approval_status"] == "pending_approval"),
            "approved": sum(1 for o in enriched if o["approval_status"] == "approved"),
            "allocated": sum(1 for o in enriched if o["allocated_quantity"] > 0),
            "in_transit": sum(1 for o in enriched if o["delivery_status"] in {"dispatched", "in_transit"}),
            "delivered": sum(1 for o in enriched if o["delivery_status"] == "delivered" or o["status"] == "fulfilled"),
            "partially_fulfilled": sum(
                1 for o in enriched if o["delivery_status"] == "partially_delivered" or o["status"] == "partially_fulfilled"
            ),
            "rejected": sum(1 for o in enriched if o["approval_status"] == "rejected"),
        },
        "recent_orders": enriched[:8],
    }


@router.get("/profile")
def get_hospital_profile(
    user: User = Depends(require_hospital_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    hospital = _get_bound_hospital(db, user)
    return {
        "id": hospital.id,
        "code": hospital.code,
        "name": hospital.name,
        "area": hospital.area,
        "city": hospital.city,
        "latitude": hospital.latitude,
        "longitude": hospital.longitude,
        "priority_level": hospital.priority_level,
        "bed_capacity": hospital.bed_capacity,
        "status": hospital.status,
        "contact_user": {
            "full_name": user.full_name,
            "email": user.email,
            "phone_number": user.phone_number,
        },
    }


@router.patch("/profile")
def update_hospital_profile(
    payload: HospitalProfileUpdateRequest,
    request: Request,
    user: User = Depends(require_hospital_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    hospital = _get_bound_hospital(db, user)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(hospital, field, value)
    audit_service.log_audit_event(
        db,
        actor=user,
        action="hospital.profile_updated",
        target_entity="hospital",
        target_id=hospital.id,
        metadata=updates,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(hospital)
    return get_hospital_profile(user=user, db=db)


@router.get("/products")
def list_catalog_products(
    _user: User = Depends(require_hospital_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    products = list(db.scalars(select(Product).order_by(Product.code)).all())
    return [
        {
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "category": p.category,
            "unit": p.unit,
            "unit_weight_kg": p.unit_weight_kg,
            "cold_chain_required": p.cold_chain_required,
        }
        for p in products
    ]


@router.post("/orders", status_code=status.HTTP_201_CREATED)
def create_hospital_order(
    payload: HospitalOrderCreateRequest,
    request: Request,
    user: User = Depends(require_hospital_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Submit a single- or multi-product medical supply order for the user's own hospital.
    Always enters `pending_approval` — hospitals can NEVER create pre-approved orders.
    """
    hospital = _get_bound_hospital(db, user)
    order_group_code = f"ORD-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:5].upper()}"

    created_demands: list[Demand] = []
    seen_prods: set[int] = set()
    for idx, line in enumerate(payload.items, start=1):
        if line.product_id in seen_prods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate product lines in a single order submission are not allowed.",
            )
        seen_prods.add(line.product_id)
        prod = db.get(Product, line.product_id)
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medical product id={line.product_id} does not exist.",
            )

        demand_code = f"DEM-{uuid4().hex[:8].upper()}"
        dem = Demand(
            demand_code=demand_code,
            order_group_code=order_group_code,
            hospital_id=hospital.id,
            product_id=prod.id,
            quantity_requested=line.quantity_requested,
            priority_level=payload.priority_level,
            status="pending_approval",
            approval_status="pending_approval",
            emergency_reason=payload.emergency_reason.strip() if payload.emergency_reason else None,
            required_by=payload.required_by,
            submitted_by_user_id=user.id,
            data_note=payload.data_note or f"Hospital Portal Order ({order_group_code})",
        )
        db.add(dem)
        created_demands.append(dem)

    db.flush()
    audit_service.notify_users_by_role(
        db,
        role="admin",
        title=f"New {payload.priority_level.upper()} Order Pending Approval",
        message=(
            f"{hospital.code} ({hospital.name}) submitted {order_group_code} "
            f"with {len(created_demands)} product line(s) awaiting Admin approval."
        ),
        category="order",
        entity_type="demand",
        entity_id=created_demands[0].id,
    )
    audit_service.log_audit_event(
        db,
        actor=user,
        action="hospital.order_submitted",
        target_entity="demand",
        target_id=order_group_code,
        metadata={
            "hospital_code": hospital.code,
            "priority_level": payload.priority_level,
            "line_count": len(created_demands),
        },
        ip_address=get_client_ip(request),
    )
    db.commit()
    for d in created_demands:
        db.refresh(d)

    return {
        "order_group_code": order_group_code,
        "approval_status": "pending_approval",
        "message": "Order submitted and queued for Administrator review.",
        "orders": _build_order_tracking_view(db, hospital, created_demands),
    }


@router.get("/orders")
def list_my_hospital_orders(
    priority_level: str | None = Query(default=None),
    approval_status: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    user: User = Depends(require_hospital_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """List orders strictly belonging to the authenticated hospital user's own hospital."""
    hospital = _get_bound_hospital(db, user)
    stmt = (
        select(Demand)
        .where(Demand.hospital_id == hospital.id)
        .order_by(Demand.created_at.desc(), Demand.id.desc())
    )
    if priority_level:
        stmt = stmt.where(Demand.priority_level == priority_level.lower())
    if status_filter:
        stmt = stmt.where(Demand.status == status_filter.lower())
    demands = list(db.scalars(stmt).all())
    enriched = _build_order_tracking_view(db, hospital, demands)
    if approval_status:
        enriched = [o for o in enriched if o["approval_status"] == approval_status.lower()]
    return enriched


@router.get("/orders/{demand_id}")
def get_my_hospital_order_detail(
    demand_id: int,
    user: User = Depends(require_hospital_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Retrieve a single order strictly owned by the authenticated user's hospital."""
    hospital = _get_bound_hospital(db, user)
    demand = db.get(Demand, demand_id)
    if not demand:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    if demand.hospital_id != hospital.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You may only inspect orders belonging to your own hospital.",
        )
    return _build_order_tracking_view(db, hospital, [demand])[0]
