"""Performance Analytics API routes (/api/analytics)."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.demand import Demand
from app.models.hospital import Hospital
from app.models.inventory import Inventory
from app.models.optimization_run import OptimizationRun
from app.models.product import Product
from app.models.warehouse import Warehouse

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Compute live operational KPIs directly from database records.

    Never returns hardcoded metrics. When no optimization run has been
    executed yet, cost/fulfillment fields explicitly return None.
    """
    total_warehouses = db.scalar(select(func.count(Warehouse.id))) or 0
    total_hospitals = db.scalar(select(func.count(Hospital.id))) or 0
    critical_hospitals = (
        db.scalar(
            select(func.count(Hospital.id)).where(Hospital.priority_level == "critical")
        )
        or 0
    )
    total_available_inventory = (
        db.scalar(select(func.coalesce(func.sum(Inventory.quantity_available), 0))) or 0
    )
    total_storage_capacity = (
        db.scalar(select(func.coalesce(func.sum(Warehouse.storage_capacity_units), 0))) or 0
    )
    total_open_demand = (
        db.scalar(
            select(func.coalesce(func.sum(Demand.quantity_requested), 0)).where(
                Demand.status == "open"
            )
        )
        or 0
    )

    latest_run = db.scalar(
        select(OptimizationRun)
        .order_by(OptimizationRun.created_at.desc(), OptimizationRun.id.desc())
        .limit(1)
    )

    inventory_utilization_pct = (
        round((total_available_inventory / total_storage_capacity) * 100.0, 2)
        if total_storage_capacity > 0
        else 0.0
    )

    fulfillment_pct: float | None = None
    latest_distribution_cost: float | None = None
    if latest_run:
        denom = latest_run.total_allocated + latest_run.total_unmet_demand
        fulfillment_pct = round((latest_run.total_allocated / denom) * 100.0, 2) if denom > 0 else 100.0
        latest_distribution_cost = latest_run.total_cost

    return {
        "total_warehouses": int(total_warehouses),
        "total_hospitals": int(total_hospitals),
        "critical_hospital_alerts": int(critical_hospitals),
        "available_inventory_units": int(total_available_inventory),
        "total_open_demand_units": int(total_open_demand),
        "inventory_utilization_pct": inventory_utilization_pct,
        "latest_demand_fulfillment_pct": fulfillment_pct,
        "latest_distribution_cost": latest_distribution_cost,
        "latest_run_code": latest_run.run_code if latest_run else None,
        "data_source_note": "Computed live from seeded synthetic simulation tables.",
    }


@router.get("/supply-demand-gap")
def get_supply_demand_gap(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """Return product-wise aggregate available supply vs. open hospital demand."""
    products = list(db.scalars(select(Product).order_by(Product.code)).all())
    inventories = list(db.scalars(select(Inventory)).all())
    demands = list(db.scalars(select(Demand).where(Demand.status == "open")).all())

    supply_by_prod: dict[int, int] = defaultdict(int)
    for inv in inventories:
        supply_by_prod[inv.product_id] += max(0, inv.quantity_available - inv.quantity_reserved)

    demand_by_prod: dict[int, int] = defaultdict(int)
    for dem in demands:
        demand_by_prod[dem.product_id] += dem.quantity_requested

    results: list[dict[str, Any]] = []
    for prod in products:
        sup = supply_by_prod[prod.id]
        dem = demand_by_prod[prod.id]
        results.append(
            {
                "product_code": prod.code,
                "product_name": prod.name,
                "unit": prod.unit,
                "total_supply": sup,
                "total_open_demand": dem,
                "net_balance": sup - dem,
                "shortage_flag": sup < dem,
            }
        )
    return results
