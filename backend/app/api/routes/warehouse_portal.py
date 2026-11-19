"""
Warehouse Portal API (/api/warehouse) — Strictly scoped to authenticated WAREHOUSE user's depot.

Enforces:
- Cross-warehouse isolation (cannot view or edit another warehouse's stock or shipments).
- Non-negative physical stock & traceable StockMovement records for stock-in/adjustments.
- Warehouse status transitions (`active` | `inactive` | `maintenance`): inactive/maintenance
  excludes the warehouse from new optimization runs while preserving stock, history, and
  in-progress dispatches.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_warehouse_user
from app.database.connection import get_db
from app.models.allocation import Allocation
from app.models.dispatch import DispatchPlan, VehicleAssignment
from app.models.hospital import Hospital
from app.models.inventory import Inventory
from app.models.optimization_run import OptimizationRun
from app.models.platform import StockMovement
from app.models.product import Product
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse
from app.services import audit_service, onboarding_service

router = APIRouter(prefix="/api/warehouse", tags=["Warehouse Portal"])


class WarehouseProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    area: str | None = Field(default=None, min_length=2, max_length=80)
    storage_capacity_units: int | None = Field(default=None, gt=0)


class WarehouseStatusPatch(BaseModel):
    status: Literal["active", "inactive", "maintenance"]
    reason: str | None = Field(default=None, max_length=255)


class WarehouseStockAdjustRequest(BaseModel):
    movement_type: Literal["stock_in", "adjustment"] = "stock_in"
    quantity_delta: int | None = None  # Used for stock_in (+) or relative adjustment (+/-)
    new_quantity_available: int | None = Field(default=None, ge=0)
    reorder_level: int | None = Field(default=None, ge=0)
    reason: str = Field(..., min_length=3, max_length=255)


class WarehouseStockCreateRequest(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity_available: int = Field(..., ge=0)
    reorder_level: int = Field(default=100, ge=0)
    reason: str = Field(default="Initial stock entry via Warehouse Portal", max_length=255)


class WarehouseNewMedicineRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    category: str = Field(default="essential_medicine", min_length=2, max_length=64)
    unit: str = Field(default="box", min_length=1, max_length=32)
    unit_weight_kg: float = Field(default=1.0, gt=0.0, le=500.0)
    base_transport_cost_per_km: float = Field(default=2.5, ge=0.0, le=500.0)
    quantity_available: int = Field(..., ge=0)
    reorder_level: int = Field(default=50, ge=0)
    reason: str = Field(default="New medicine added via Warehouse Portal", max_length=255)


class ShipmentPreparationPatch(BaseModel):
    preparation_status: Literal["pending", "preparing", "ready_for_dispatch", "handed_over"]
    preparation_notes: str | None = Field(default=None, max_length=255)


def _get_bound_warehouse(db: Session, user: User) -> Warehouse:
    if not user.associated_warehouse_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not associated with any warehouse. Contact an administrator.",
        )
    wh = db.get(Warehouse, user.associated_warehouse_id)
    if not wh:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Associated warehouse record not found."
        )
    return wh


@router.get("/dashboard")
def warehouse_dashboard(
    user: User = Depends(require_warehouse_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Warehouse-scoped operational KPIs distinguishing physical, reserved, and net available stock."""
    wh = _get_bound_warehouse(db, user)
    inv_rows = list(db.scalars(select(Inventory).where(Inventory.warehouse_id == wh.id)).all())
    prods = {p.id: p for p in db.scalars(select(Product)).all()}

    total_physical = sum(int(i.quantity_available) for i in inv_rows)
    total_reserved = sum(int(i.quantity_reserved) for i in inv_rows)
    total_net_available = sum(max(0, int(i.quantity_available) - int(i.quantity_reserved)) for i in inv_rows)
    low_stock_items = [
        {
            "inventory_id": i.id,
            "product_code": prods[i.product_id].code if i.product_id in prods else f"PROD-{i.product_id}",
            "product_name": prods[i.product_id].name if i.product_id in prods else "",
            "quantity_available": i.quantity_available,
            "reorder_level": i.reorder_level,
            "out_of_stock": i.quantity_available == 0,
        }
        for i in inv_rows
        if i.quantity_available <= i.reorder_level
    ]

    assignments = list(
        db.scalars(
            select(VehicleAssignment)
            .where(VehicleAssignment.warehouse_id == wh.id)
            .order_by(VehicleAssignment.created_at.desc(), VehicleAssignment.id.desc())
        ).all()
    )
    pending_prep = sum(
        1
        for a in assignments
        if (a.preparation_status or "pending") in {"pending", "preparing"}
        and a.status not in {"delivered", "cancelled"}
    )
    active_dispatches = sum(
        1 for a in assignments if a.status in {"planned", "dispatched", "in_transit", "partially_delivered"}
    )

    return {
        "warehouse": {
            "id": wh.id,
            "code": wh.code,
            "name": wh.name,
            "area": wh.area,
            "city": wh.city,
            "storage_capacity_units": wh.storage_capacity_units,
            "status": wh.status,
        },
        "kpis": {
            "product_count": len(inv_rows),
            "total_physical_stock": total_physical,
            "total_reserved_stock": total_reserved,
            "total_available_stock": total_net_available,
            "low_stock_count": len(low_stock_items),
            "out_of_stock_count": sum(1 for item in low_stock_items if item["out_of_stock"]),
            "pending_preparation": pending_prep,
            "active_dispatches": active_dispatches,
            "utilization_pct": round((total_physical / wh.storage_capacity_units) * 100.0, 2)
            if wh.storage_capacity_units > 0
            else 0.0,
        },
        "low_stock_alerts": low_stock_items,
    }


@router.get("/profile")
def get_warehouse_profile(
    user: User = Depends(require_warehouse_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    wh = _get_bound_warehouse(db, user)
    return {
        "id": wh.id,
        "code": wh.code,
        "name": wh.name,
        "area": wh.area,
        "city": wh.city,
        "latitude": wh.latitude,
        "longitude": wh.longitude,
        "storage_capacity_units": wh.storage_capacity_units,
        "status": wh.status,
        "manager": {
            "full_name": user.full_name,
            "email": user.email,
            "phone_number": user.phone_number,
        },
    }


@router.patch("/profile")
def update_warehouse_profile(
    payload: WarehouseProfilePatch,
    request: Request,
    user: User = Depends(require_warehouse_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    wh = _get_bound_warehouse(db, user)
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(wh, k, v)
    audit_service.log_audit_event(
        db,
        actor=user,
        action="warehouse.profile_updated",
        target_entity="warehouse",
        target_id=wh.id,
        metadata=updates,
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(wh)
    return get_warehouse_profile(user=user, db=db)


@router.patch("/status")
def update_warehouse_status(
    payload: WarehouseStatusPatch,
    request: Request,
    user: User = Depends(require_warehouse_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Transition own warehouse between ACTIVE, INACTIVE, and MAINTENANCE.
    Inactive/maintenance warehouses are automatically excluded from new optimization runs
    without losing inventory, history, or cancelling in-progress dispatches.
    """
    wh = _get_bound_warehouse(db, user)
    old_status = wh.status
    wh.status = payload.status

    if payload.status != old_status:
        audit_service.notify_users_by_role(
            db,
            role="admin",
            title=f"Warehouse {wh.code} Status Changed to {payload.status.upper()}",
            message=(
                f"{wh.code} ({wh.name}) was updated from {old_status.upper()} to "
                f"{payload.status.upper()} by {user.full_name}."
                + (f" Reason: {payload.reason}" if payload.reason else "")
            ),
            category="warehouse",
            entity_type="warehouse",
            entity_id=wh.id,
        )
    audit_service.log_audit_event(
        db,
        actor=user,
        action="warehouse.status_changed",
        target_entity="warehouse",
        target_id=wh.id,
        metadata={"old_status": old_status, "new_status": payload.status, "reason": payload.reason},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {
        "warehouse_id": wh.id,
        "warehouse_code": wh.code,
        "status": wh.status,
        "note": (
            "Warehouse is excluded from new optimization runs while inactive/maintenance; "
            "existing inventory, history, and in-progress dispatches remain preserved."
            if wh.status != "active"
            else "Warehouse is active and eligible for optimization."
        ),
    }


@router.get("/inventory")
def list_my_warehouse_inventory(
    user: User = Depends(require_warehouse_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    wh = _get_bound_warehouse(db, user)
    prods = {p.id: p for p in db.scalars(select(Product)).all()}
    items = list(
        db.scalars(
            select(Inventory)
            .where(Inventory.warehouse_id == wh.id)
            .order_by(Inventory.inventory_code)
        ).all()
    )
    return [
        {
            "id": i.id,
            "inventory_code": i.inventory_code,
            "warehouse_id": i.warehouse_id,
            "warehouse_code": wh.code,
            "product_id": i.product_id,
            "product_code": prods[i.product_id].code if i.product_id in prods else f"PROD-{i.product_id}",
            "product_name": prods[i.product_id].name if i.product_id in prods else "",
            "unit": prods[i.product_id].unit if i.product_id in prods else "units",
            "quantity_available": i.quantity_available,
            "quantity_reserved": i.quantity_reserved,
            "net_available": max(0, i.quantity_available - i.quantity_reserved),
            "reorder_level": i.reorder_level,
            "low_stock": i.quantity_available <= i.reorder_level,
            "updated_at": i.updated_at.isoformat() if i.updated_at else None,
        }
        for i in items
    ]


@router.get("/products")
def list_warehouse_products(
    _user: User = Depends(require_warehouse_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    return [
        {"id": p.id, "code": p.code, "name": p.name, "unit": p.unit}
        for p in db.scalars(select(Product).order_by(Product.code)).all()
    ]


@router.post("/inventory", status_code=status.HTTP_201_CREATED)
def add_new_warehouse_inventory_item(
    payload: WarehouseStockCreateRequest,
    request: Request,
    user: User = Depends(require_warehouse_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Add a new product stock entry strictly inside the user's own warehouse."""
    wh = _get_bound_warehouse(db, user)
    prod = db.get(Product, payload.product_id)
    if not prod:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    existing = db.scalar(
        select(Inventory).where(
            Inventory.warehouse_id == wh.id, Inventory.product_id == prod.id
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This product already exists in your warehouse inventory; use stock adjustment instead.",
        )

    inv = Inventory(
        inventory_code=f"INV-{wh.code}-{prod.code}-{uuid4().hex[:4].upper()}",
        warehouse_id=wh.id,
        product_id=prod.id,
        quantity_available=payload.quantity_available,
        quantity_reserved=0,
        reorder_level=payload.reorder_level,
    )
    db.add(inv)
    db.flush()
    db.add(
        StockMovement(
            inventory_id=inv.id,
            warehouse_id=wh.id,
            product_id=prod.id,
            actor_user_id=user.id,
            movement_type="stock_in",
            quantity_delta=payload.quantity_available,
            quantity_before=0,
            quantity_after=payload.quantity_available,
            reason=payload.reason,
        )
    )
    audit_service.log_audit_event(
        db,
        actor=user,
        action="warehouse.inventory_created",
        target_entity="inventory",
        target_id=inv.id,
        metadata={"warehouse_code": wh.code, "product_code": prod.code, "qty": payload.quantity_available},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {"id": inv.id, "inventory_code": inv.inventory_code, "quantity_available": inv.quantity_available}


@router.patch("/inventory/{inventory_id}")
def adjust_my_warehouse_inventory(
    inventory_id: int,
    payload: WarehouseStockAdjustRequest,
    request: Request,
    user: User = Depends(require_warehouse_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Controlled stock-in or adjustment strictly on own warehouse inventory.
    Prevents negative physical stock and records traceable StockMovement history.
    """
    wh = _get_bound_warehouse(db, user)
    inv = db.get(Inventory, inventory_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory record not found.")
    if inv.warehouse_id != wh.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You cannot modify another warehouse's inventory.",
        )

    before_qty = int(inv.quantity_available)
    if payload.new_quantity_available is not None:
        after_qty = int(payload.new_quantity_available)
        delta = after_qty - before_qty
    elif payload.quantity_delta is not None:
        if payload.movement_type == "stock_in" and payload.quantity_delta <= 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Stock-in quantity delta must be positive.",
            )
        delta = int(payload.quantity_delta)
        after_qty = before_qty + delta
    else:
        after_qty = before_qty
        delta = 0

    if after_qty < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Adjustment rejected: resulting stock ({after_qty}) cannot be negative.",
        )
    if after_qty < int(inv.quantity_reserved):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Resulting stock ({after_qty}) cannot be less than reserved stock "
                f"({inv.quantity_reserved})."
            ),
        )

    inv.quantity_available = after_qty
    if payload.reorder_level is not None:
        inv.reorder_level = payload.reorder_level

    db.add(
        StockMovement(
            inventory_id=inv.id,
            warehouse_id=wh.id,
            product_id=inv.product_id,
            actor_user_id=user.id,
            movement_type=payload.movement_type,
            quantity_delta=delta,
            quantity_before=before_qty,
            quantity_after=after_qty,
            reason=payload.reason.strip(),
        )
    )
    audit_service.log_audit_event(
        db,
        actor=user,
        action="warehouse.inventory_adjusted",
        target_entity="inventory",
        target_id=inv.id,
        metadata={
            "warehouse_code": wh.code,
            "before": before_qty,
            "after": after_qty,
            "delta": delta,
            "reason": payload.reason.strip(),
        },
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(inv)
    return {
        "id": inv.id,
        "quantity_available": inv.quantity_available,
        "quantity_reserved": inv.quantity_reserved,
        "net_available": max(0, inv.quantity_available - inv.quantity_reserved),
        "reorder_level": inv.reorder_level,
    }


@router.post("/products-with-stock", status_code=status.HTTP_201_CREATED)
def add_new_medicine_and_stock(
    payload: WarehouseNewMedicineRequest,
    request: Request,
    user: User = Depends(require_warehouse_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Create a brand-new medical product in the shared catalog and immediately stock it
    in the authenticated warehouse manager's depot with a traceable StockMovement log.
    """
    wh = _get_bound_warehouse(db, user)
    existing_prods = list(db.scalars(select(Product)).all())
    normalized_name = payload.name.strip().lower()
    if any(p.name.strip().lower() == normalized_name for p in existing_prods):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A medical product named '{payload.name.strip()}' already exists in the catalog.",
        )

    prod_code = onboarding_service.generate_next_code(
        [p.code for p in existing_prods], "PROD", pad=2
    )
    prod = Product(
        code=prod_code,
        name=payload.name.strip(),
        category=payload.category.strip() or "essential_medicine",
        unit=payload.unit.strip() or "box",
        unit_weight_kg=payload.unit_weight_kg,
        base_transport_cost_per_km=payload.base_transport_cost_per_km,
    )
    db.add(prod)
    db.flush()

    inv_code = f"INV-{wh.code}-{prod.code}-{uuid4().hex[:4].upper()}"
    inv = Inventory(
        inventory_code=inv_code,
        warehouse_id=wh.id,
        product_id=prod.id,
        quantity_available=payload.quantity_available,
        quantity_reserved=0,
        reorder_level=payload.reorder_level,
    )
    db.add(inv)
    db.flush()

    db.add(
        StockMovement(
            inventory_id=inv.id,
            warehouse_id=wh.id,
            product_id=prod.id,
            actor_user_id=user.id,
            movement_type="stock_in",
            quantity_delta=payload.quantity_available,
            quantity_before=0,
            quantity_after=payload.quantity_available,
            reason=payload.reason.strip(),
        )
    )
    audit_service.log_audit_event(
        db,
        actor=user,
        action="warehouse.medicine_created",
        target_entity="product",
        target_id=prod.id,
        metadata={
            "warehouse_code": wh.code,
            "product_code": prod.code,
            "product_name": prod.name,
            "initial_quantity": payload.quantity_available,
        },
        ip_address=get_client_ip(request),
    )
    db.commit()
    db.refresh(prod)
    db.refresh(inv)
    return {
        "product": {
            "id": prod.id,
            "code": prod.code,
            "name": prod.name,
            "category": prod.category,
            "unit": prod.unit,
            "unit_weight_kg": prod.unit_weight_kg,
        },
        "inventory": {
            "id": inv.id,
            "inventory_code": inv.inventory_code,
            "product_id": prod.id,
            "product_code": prod.code,
            "product_name": prod.name,
            "unit": prod.unit,
            "quantity_available": inv.quantity_available,
            "quantity_reserved": inv.quantity_reserved,
            "net_available": inv.quantity_available,
            "reorder_level": inv.reorder_level,
        },
    }


@router.get("/stock-movements")
def list_my_stock_movements(
    user: User = Depends(require_warehouse_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    wh = _get_bound_warehouse(db, user)
    prods = {p.id: p for p in db.scalars(select(Product)).all()}
    users = {u.id: u for u in db.scalars(select(User)).all()}
    rows = list(
        db.scalars(
            select(StockMovement)
            .where(StockMovement.warehouse_id == wh.id)
            .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
            .limit(100)
        ).all()
    )
    return [
        {
            "id": m.id,
            "inventory_id": m.inventory_id,
            "product_code": prods[m.product_id].code if m.product_id in prods else f"PROD-{m.product_id}",
            "product_name": prods[m.product_id].name if m.product_id in prods else "",
            "movement_type": m.movement_type,
            "quantity_delta": m.quantity_delta,
            "quantity_before": m.quantity_before,
            "quantity_after": m.quantity_after,
            "reason": m.reason,
            "actor_name": users[m.actor_user_id].full_name if m.actor_user_id in users else "System",
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in rows
    ]


@router.get("/allocations")
def list_my_warehouse_allocations(
    user: User = Depends(require_warehouse_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Return latest optimal run allocations originating from this warehouse only."""
    wh = _get_bound_warehouse(db, user)
    latest_run = db.scalar(
        select(OptimizationRun)
        .where(OptimizationRun.solver_status == "Optimal")
        .order_by(OptimizationRun.created_at.desc(), OptimizationRun.id.desc())
        .limit(1)
    )
    if not latest_run:
        return {"run_code": None, "allocations": []}

    hosps = {h.id: h for h in db.scalars(select(Hospital)).all()}
    prods = {p.id: p for p in db.scalars(select(Product)).all()}
    rows = list(
        db.scalars(
            select(Allocation).where(
                Allocation.optimization_run_id == latest_run.id,
                Allocation.warehouse_id == wh.id,
            )
        ).all()
    )
    return {
        "run_code": latest_run.run_code,
        "executed_at": latest_run.created_at.isoformat() if latest_run.created_at else None,
        "allocations": [
            {
                "id": a.id,
                "hospital_code": hosps[a.hospital_id].code if a.hospital_id in hosps else f"HOSP-{a.hospital_id}",
                "hospital_name": hosps[a.hospital_id].name if a.hospital_id in hosps else "",
                "hospital_priority": hosps[a.hospital_id].priority_level if a.hospital_id in hosps else "normal",
                "product_code": prods[a.product_id].code if a.product_id in prods else f"PROD-{a.product_id}",
                "product_name": prods[a.product_id].name if a.product_id in prods else "",
                "unit": prods[a.product_id].unit if a.product_id in prods else "units",
                "quantity_allocated": a.quantity_allocated,
                "transport_cost": a.transport_cost,
            }
            for a in rows
        ],
    }


@router.get("/shipments")
def list_my_outgoing_shipments(
    user: User = Depends(require_warehouse_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    """List outgoing vehicle dispatch shipments strictly for the user's own warehouse."""
    wh = _get_bound_warehouse(db, user)
    plans = {p.id: p for p in db.scalars(select(DispatchPlan)).all()}
    vehs = {v.id: v for v in db.scalars(select(Vehicle)).all()}
    hosps = {h.id: h for h in db.scalars(select(Hospital)).all()}
    prods = {p.id: p for p in db.scalars(select(Product)).all()}
    users = {u.id: u for u in db.scalars(select(User)).all()}

    assignments = list(
        db.scalars(
            select(VehicleAssignment)
            .where(VehicleAssignment.warehouse_id == wh.id)
            .order_by(VehicleAssignment.created_at.desc(), VehicleAssignment.id.desc())
        ).all()
    )
    out: list[dict[str, Any]] = []
    for va in assignments:
        plan = plans.get(va.dispatch_plan_id)
        veh = vehs.get(va.vehicle_id)
        drv_id = va.assigned_driver_user_id or (veh.assigned_driver_user_id if veh else None)
        drv = users.get(drv_id) if drv_id else None
        stops_payload = []
        for s in va.delivery_stops:
            hosp = hosps.get(s.hospital_id)
            stops_payload.append(
                {
                    "stop_id": s.id,
                    "stop_sequence": s.stop_sequence,
                    "hospital_code": hosp.code if hosp else f"HOSP-{s.hospital_id}",
                    "hospital_name": hosp.name if hosp else "",
                    "priority_level": hosp.priority_level if hosp else "normal",
                    "status": s.status,
                    "stop_weight_kg": s.stop_weight_kg,
                    "shipment_lines": [
                        {
                            "product_code": prods[ln.product_id].code if ln.product_id in prods else f"PROD-{ln.product_id}",
                            "product_name": prods[ln.product_id].name if ln.product_id in prods else "",
                            "unit": prods[ln.product_id].unit if ln.product_id in prods else "units",
                            "quantity_planned": ln.quantity_planned,
                            "quantity_delivered": ln.quantity_delivered,
                        }
                        for ln in s.shipment_lines
                    ],
                }
            )
        out.append(
            {
                "assignment_id": va.id,
                "dispatch_plan_id": va.dispatch_plan_id,
                "plan_code": plan.plan_code if plan else f"DSP-{va.dispatch_plan_id}",
                "vehicle_code": veh.vehicle_code if veh else f"VEH-{va.vehicle_id}",
                "vehicle_type": veh.vehicle_type if veh else "medical_van",
                "driver_name": drv.full_name if drv else "Unassigned",
                "trip_number": va.trip_number,
                "total_load_kg": va.total_load_kg,
                "capacity_kg": va.capacity_kg,
                "utilization_pct": va.utilization_pct,
                "dispatch_status": va.status,
                "preparation_status": va.preparation_status or "pending",
                "preparation_notes": va.preparation_notes,
                "prepared_at": va.prepared_at.isoformat() if va.prepared_at else None,
                "stops": stops_payload,
                "created_at": va.created_at.isoformat() if va.created_at else None,
            }
        )
    return out


@router.patch("/shipments/{assignment_id}/preparation")
def update_shipment_preparation(
    assignment_id: int,
    payload: ShipmentPreparationPatch,
    request: Request,
    user: User = Depends(require_warehouse_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Update preparation status for an outgoing shipment owned by this warehouse."""
    wh = _get_bound_warehouse(db, user)
    va = db.get(VehicleAssignment, assignment_id)
    if not va:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment assignment not found.")
    if va.warehouse_id != wh.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Shipment belongs to a different warehouse.",
        )

    va.preparation_status = payload.preparation_status
    if payload.preparation_notes is not None:
        va.preparation_notes = payload.preparation_notes.strip() or None
    if payload.preparation_status in {"ready_for_dispatch", "handed_over"}:
        va.prepared_at = datetime.now(timezone.utc)

    veh = db.get(Vehicle, va.vehicle_id)
    drv_id = va.assigned_driver_user_id or (veh.assigned_driver_user_id if veh else None)
    if payload.preparation_status == "ready_for_dispatch":
        if drv_id:
            audit_service.create_notification(
                db,
                user_id=drv_id,
                title=f"Shipment Ready for Pickup at {wh.code}",
                message=f"Vehicle assignment #{va.id} ({veh.vehicle_code if veh else ''}) is packed and ready at {wh.name}.",
                category="dispatch",
                entity_type="vehicle_assignment",
                entity_id=va.id,
            )
        audit_service.notify_users_by_role(
            db,
            role="admin",
            title=f"Warehouse {wh.code} Shipment Ready",
            message=f"Assignment #{va.id} at {wh.code} marked ready for dispatch by {user.full_name}.",
            category="dispatch",
            entity_type="vehicle_assignment",
            entity_id=va.id,
        )

    audit_service.log_audit_event(
        db,
        actor=user,
        action="warehouse.shipment_preparation_updated",
        target_entity="vehicle_assignment",
        target_id=va.id,
        metadata={"preparation_status": va.preparation_status, "warehouse_code": wh.code},
        ip_address=get_client_ip(request),
    )
    db.commit()
    return {
        "assignment_id": va.id,
        "preparation_status": va.preparation_status,
        "preparation_notes": va.preparation_notes,
        "prepared_at": va.prepared_at.isoformat() if va.prepared_at else None,
    }
