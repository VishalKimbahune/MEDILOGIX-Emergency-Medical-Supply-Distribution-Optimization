"""
Delivery Portal API (/api/delivery) — Strictly scoped to authenticated DELIVERY user's assignments.

Enforces:
- Strict assignment & stop ownership (a driver can NEVER view or confirm another driver's route).
- Existing validated dispatch lifecycle (`planned`, `dispatched`, `in_transit`,
  `partially_delivered`, `delivered`, `cancelled`).
- Non-negative delivery confirmation capped at `quantity_planned`.
- Duplicate/re-confirmation guard preventing accidental overwrite of already-delivered stops.
- Does NOT automatically deduct warehouse inventory (documented limitation).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_delivery_user
from app.database.connection import get_db
from app.models.dispatch import DeliveryStop, DispatchPlan, VehicleAssignment
from app.models.hospital import Hospital
from app.models.product import Product
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse
from app.schemas.dispatch import ShipmentLineDeliveryUpdate, StopStatusUpdateRequest
from app.services import audit_service, dispatch_service

router = APIRouter(prefix="/api/delivery", tags=["Delivery Portal"])


class DeliveryConfirmationItem(BaseModel):
    shipment_line_id: int = Field(..., gt=0)
    quantity_delivered: float = Field(..., ge=0.0)


class DeliveryConfirmationRequest(BaseModel):
    remarks: str | None = Field(default=None, max_length=255)
    items: list[DeliveryConfirmationItem] = Field(..., min_length=1)


def _driver_vehicle_ids(db: Session, user_id: int) -> set[int]:
    return {
        v.id
        for v in db.scalars(select(Vehicle).where(Vehicle.assigned_driver_user_id == user_id)).all()
    }


def _assignment_belongs_to_driver(va: VehicleAssignment, user_id: int, driver_veh_ids: set[int]) -> bool:
    if va.assigned_driver_user_id is not None:
        return va.assigned_driver_user_id == user_id
    return va.vehicle_id in driver_veh_ids


def _get_driver_assignments(db: Session, user: User) -> list[VehicleAssignment]:
    veh_ids = _driver_vehicle_ids(db, user.id)
    all_va = list(
        db.scalars(
            select(VehicleAssignment).order_by(
                VehicleAssignment.created_at.desc(), VehicleAssignment.id.desc()
            )
        ).all()
    )
    return [va for va in all_va if _assignment_belongs_to_driver(va, user.id, veh_ids)]


def _serialize_driver_assignment(db: Session, va: VehicleAssignment) -> dict[str, Any]:
    plan = db.get(DispatchPlan, va.dispatch_plan_id)
    veh = db.get(Vehicle, va.vehicle_id)
    wh = db.get(Warehouse, va.warehouse_id)
    hosps = {h.id: h for h in db.scalars(select(Hospital)).all()}
    prods = {p.id: p for p in db.scalars(select(Product)).all()}

    geom_meta = va.route_geometry_json if isinstance(va.route_geometry_json, dict) else {}
    raw_coords = va.route_coordinates_json or []
    route_geom = geom_meta.get("geometry") or [
        [pt["lat"], pt["lon"]]
        for pt in raw_coords
        if isinstance(pt, dict) and "lat" in pt and "lon" in pt
    ]
    plan_summary = (plan.summary_json or {}) if plan else {}
    source = geom_meta.get("routing_source", plan_summary.get("routing_source", "synthetic_fallback"))

    stops_out = []
    for s in va.delivery_stops:
        hosp = hosps.get(s.hospital_id)
        stops_out.append(
            {
                "id": s.id,
                "stop_sequence": s.stop_sequence,
                "hospital_id": s.hospital_id,
                "hospital_code": hosp.code if hosp else f"HOSP-{s.hospital_id}",
                "hospital_name": hosp.name if hosp else "",
                "hospital_area": hosp.area if hosp else "",
                "priority_level": hosp.priority_level if hosp else "normal",
                "latitude": hosp.latitude if hosp else 0.0,
                "longitude": hosp.longitude if hosp else 0.0,
                "status": s.status,
                "leg_distance_km": s.leg_distance_km,
                "cumulative_distance_km": s.cumulative_distance_km,
                "estimated_arrival_min": s.estimated_arrival_min,
                "stop_weight_kg": s.stop_weight_kg,
                "notes": s.notes,
                "confirmed_at": s.confirmed_at.isoformat() if s.confirmed_at else None,
                "shipment_lines": [
                    {
                        "id": ln.id,
                        "product_id": ln.product_id,
                        "product_code": prods[ln.product_id].code if ln.product_id in prods else f"PROD-{ln.product_id}",
                        "product_name": prods[ln.product_id].name if ln.product_id in prods else "",
                        "unit": prods[ln.product_id].unit if ln.product_id in prods else "units",
                        "quantity_planned": ln.quantity_planned,
                        "quantity_delivered": ln.quantity_delivered,
                        "quantity_remaining": round(max(0.0, ln.quantity_planned - ln.quantity_delivered), 4),
                        "total_weight_kg": ln.total_weight_kg,
                    }
                    for ln in s.shipment_lines
                ],
            }
        )

    return {
        "id": va.id,
        "dispatch_plan_id": va.dispatch_plan_id,
        "plan_code": plan.plan_code if plan else f"DSP-{va.dispatch_plan_id}",
        "plan_status": plan.status if plan else va.status,
        "vehicle_id": va.vehicle_id,
        "vehicle_code": veh.vehicle_code if veh else f"VEH-{va.vehicle_id}",
        "vehicle_type": veh.vehicle_type if veh else "medical_van",
        "warehouse_id": va.warehouse_id,
        "warehouse_code": wh.code if wh else f"WH-{va.warehouse_id}",
        "warehouse_name": wh.name if wh else "",
        "warehouse_area": wh.area if wh else "",
        "warehouse_lat": wh.latitude if wh else 0.0,
        "warehouse_lon": wh.longitude if wh else 0.0,
        "trip_number": va.trip_number,
        "status": va.status,
        "preparation_status": va.preparation_status or "pending",
        "total_load_kg": va.total_load_kg,
        "capacity_kg": va.capacity_kg,
        "utilization_pct": va.utilization_pct,
        "route_distance_km": va.route_distance_km,
        "estimated_duration_min": va.estimated_duration_min,
        "routing_source": source,
        "route_coordinates": raw_coords,
        "route_geometry": route_geom,
        "osm_way_ids": geom_meta.get("way_ids", []),
        "road_names": geom_meta.get("road_names", []),
        "stops": stops_out,
        "created_at": va.created_at.isoformat() if va.created_at else None,
    }


@router.get("/dashboard")
def delivery_dashboard(
    user: User = Depends(require_delivery_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Driver-scoped dashboard KPIs and assigned fleet metadata."""
    my_vehicles = list(
        db.scalars(
            select(Vehicle)
            .where(Vehicle.assigned_driver_user_id == user.id)
            .order_by(Vehicle.vehicle_code)
        ).all()
    )
    wh_map = {w.id: w for w in db.scalars(select(Warehouse)).all()}
    assignments = _get_driver_assignments(db, user)

    all_stops = [s for va in assignments for s in va.delivery_stops]
    all_lines = [ln for s in all_stops for ln in s.shipment_lines]

    return {
        "driver": {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "phone_number": user.phone_number,
        },
        "assigned_vehicles": [
            {
                "id": v.id,
                "vehicle_code": v.vehicle_code,
                "vehicle_type": v.vehicle_type,
                "capacity_kg": v.capacity_kg,
                "status": v.status,
                "warehouse_code": wh_map[v.warehouse_id].code if v.warehouse_id in wh_map else None,
                "warehouse_name": wh_map[v.warehouse_id].name if v.warehouse_id in wh_map else None,
            }
            for v in my_vehicles
        ],
        "kpis": {
            "assigned_deliveries": len(assignments),
            "pending_stops": sum(
                1 for s in all_stops if s.status in {"planned", "dispatched", "in_transit", "partially_delivered"}
            ),
            "completed_stops": sum(1 for s in all_stops if s.status == "delivered"),
            "in_transit_assignments": sum(
                1 for va in assignments if va.status in {"dispatched", "in_transit"}
            ),
            "total_planned_quantity": round(sum(float(ln.quantity_planned) for ln in all_lines), 2),
            "total_delivered_quantity": round(sum(float(ln.quantity_delivered) for ln in all_lines), 2),
        },
        "active_assignments": [
            _serialize_driver_assignment(db, va)
            for va in assignments
            if va.status not in {"delivered", "cancelled"}
        ][:5],
    }


@router.get("/assignments")
def list_my_assignments(
    user: User = Depends(require_delivery_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    """List only vehicle route assignments owned by the authenticated delivery user."""
    return [_serialize_driver_assignment(db, va) for va in _get_driver_assignments(db, user)]


@router.get("/assignments/{assignment_id}")
def get_my_assignment_detail(
    assignment_id: int,
    user: User = Depends(require_delivery_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    va = db.get(VehicleAssignment, assignment_id)
    if not va:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found.")
    if not _assignment_belongs_to_driver(va, user.id, _driver_vehicle_ids(db, user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This route assignment belongs to another delivery driver.",
        )
    return _serialize_driver_assignment(db, va)


@router.get("/stops/{stop_id}")
def get_my_stop_detail(
    stop_id: int,
    user: User = Depends(require_delivery_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    stop = db.get(DeliveryStop, stop_id)
    if not stop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery stop not found.")
    va = stop.vehicle_assignment
    if not _assignment_belongs_to_driver(va, user.id, _driver_vehicle_ids(db, user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This delivery stop belongs to another driver.",
        )
    detail = _serialize_driver_assignment(db, va)
    stop_payload = next(s for s in detail["stops"] if s["id"] == stop.id)
    return {
        "assignment_id": va.id,
        "plan_code": detail["plan_code"],
        "vehicle_code": detail["vehicle_code"],
        "warehouse_code": detail["warehouse_code"],
        "stop": stop_payload,
    }


@router.patch("/stops/{stop_id}/status")
def update_my_stop_status(
    stop_id: int,
    payload: StopStatusUpdateRequest,
    request: Request,
    user: User = Depends(require_delivery_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Advance an assigned stop's lifecycle status following validated state transitions."""
    stop = db.get(DeliveryStop, stop_id)
    if not stop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery stop not found.")
    va = stop.vehicle_assignment
    if not _assignment_belongs_to_driver(va, user.id, _driver_vehicle_ids(db, user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You can only update stops assigned to you.",
        )
    if stop.status == "delivered":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This stop has already been confirmed as delivered. Contact Admin for corrections.",
        )

    try:
        dispatch_service.update_delivery_stop_status(db, stop_id, payload)
    except dispatch_service.DispatchDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    db.refresh(stop)
    if payload.status in {"delivered", "partially_delivered"}:
        stop.confirmed_by_user_id = user.id
        stop.confirmed_at = datetime.now(timezone.utc)
        audit_service.notify_users_by_role(
            db,
            role="hospital",
            hospital_id=stop.hospital_id,
            title=f"Delivery Update — {payload.status.replace('_', ' ').title()}",
            message=f"Stop #{stop.stop_sequence} updated to {payload.status.replace('_', ' ')} by {user.full_name}.",
            category="delivery",
            entity_type="delivery_stop",
            entity_id=stop.id,
        )
    audit_service.log_audit_event(
        db,
        actor=user,
        action="delivery.stop_status_updated",
        target_entity="delivery_stop",
        target_id=stop.id,
        metadata={"status": payload.status, "notes": payload.notes},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _serialize_driver_assignment(db, va)


@router.post("/stops/{stop_id}/confirmation")
def confirm_my_delivery_stop(
    stop_id: int,
    payload: DeliveryConfirmationRequest,
    request: Request,
    user: User = Depends(require_delivery_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Record full or partial delivery quantities at an assigned stop.
    - Prevents negative or over-planned quantities.
    - Blocks duplicate re-confirmation of already-delivered stops.
    - Automatically rolls up parent assignment & dispatch plan statuses.
    """
    stop = db.get(DeliveryStop, stop_id)
    if not stop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery stop not found.")
    va = stop.vehicle_assignment
    if not _assignment_belongs_to_driver(va, user.id, _driver_vehicle_ids(db, user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. This stop does not belong to your assigned routes.",
        )
    if stop.status == "delivered":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stop already confirmed as delivered; duplicate confirmation blocked.",
        )
    if stop.status == "cancelled":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot confirm delivery on a cancelled stop.",
        )
    if stop.status == "planned":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Stop is still in 'planned' status. Dispatch the assignment before confirming delivery.",
        )

    line_by_id = {ln.id: ln for ln in stop.shipment_lines}
    for item in payload.items:
        ln = line_by_id.get(item.shipment_line_id)
        if not ln:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Shipment line id={item.shipment_line_id} does not belong to stop id={stop_id}.",
            )
        if item.quantity_delivered > ln.quantity_planned + 1e-4:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Delivered quantity ({item.quantity_delivered}) exceeds authorized planned "
                    f"quantity ({ln.quantity_planned})."
                ),
            )

    # Determine full vs. partial delivery honestly from submitted quantities
    submitted_map = {i.shipment_line_id: i.quantity_delivered for i in payload.items}
    all_full = all(
        abs(submitted_map.get(ln.id, ln.quantity_delivered) - ln.quantity_planned) <= 1e-4
        for ln in stop.shipment_lines
    )
    target_status = "delivered" if all_full else "partially_delivered"

    update_req = StopStatusUpdateRequest(
        status=target_status,  # type: ignore[arg-type]
        notes=payload.remarks,
        shipment_updates=[
            ShipmentLineDeliveryUpdate(
                shipment_line_id=i.shipment_line_id,
                quantity_delivered=i.quantity_delivered,
            )
            for i in payload.items
        ],
    )
    try:
        dispatch_service.update_delivery_stop_status(db, stop_id, update_req)
    except dispatch_service.DispatchDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    db.refresh(stop)
    stop.confirmed_by_user_id = user.id
    stop.confirmed_at = datetime.now(timezone.utc)

    hosp = db.get(Hospital, stop.hospital_id)
    audit_service.notify_users_by_role(
        db,
        role="hospital",
        hospital_id=stop.hospital_id,
        title=f"Delivery Confirmed ({target_status.replace('_', ' ').title()})",
        message=(
            f"Driver {user.full_name} recorded {target_status.replace('_', ' ')} at "
            f"{hosp.code if hosp else 'your hospital'}."
            + (f" Remarks: {payload.remarks}" if payload.remarks else "")
        ),
        category="delivery",
        entity_type="delivery_stop",
        entity_id=stop.id,
    )
    audit_service.notify_users_by_role(
        db,
        role="admin",
        title=f"Stop Delivery Confirmed — {hosp.code if hosp else f'Stop #{stop.id}'}",
        message=f"{user.full_name} recorded {target_status.replace('_', ' ')} for Stop #{stop.id}.",
        category="delivery",
        entity_type="delivery_stop",
        entity_id=stop.id,
    )
    audit_service.log_audit_event(
        db,
        actor=user,
        action="delivery.stop_confirmed",
        target_entity="delivery_stop",
        target_id=stop.id,
        metadata={
            "status": target_status,
            "remarks": payload.remarks,
            "items_count": len(payload.items),
        },
        ip_address=get_client_ip(request),
    )
    db.commit()
    return _serialize_driver_assignment(db, va)
