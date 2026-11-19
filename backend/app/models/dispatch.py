"""
Dispatch Management ORM models (Phase 4B).

Tracks persistent dispatch plans generated from completed Phase 3 optimization runs:
- DispatchPlan: Top-level dispatch plan referencing an OptimizationRun
- VehicleAssignment: Per-vehicle depot-based tour derived from OR-Tools CVRP
- DeliveryStop: Ordered hospital stops along a vehicle tour
- ShipmentLine: Product-wise planned vs. delivered quantities at each stop
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class DispatchPlan(Base, TimestampMixin):
    """Persistent multi-depot vehicle dispatch plan generated from an optimization run."""

    __tablename__ = "dispatch_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_code: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    optimization_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("optimization_runs.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="planned"
    )  # planned | dispatched | in_transit | delivered | partially_delivered | cancelled
    solver_status: Mapped[str] = mapped_column(String(40), index=True, nullable=False, default="Optimal")
    total_vehicles_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_routes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_stops: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_duration_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_weight_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    allow_multi_trip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_split_deliveries: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    # Relationships
    optimization_run = relationship("OptimizationRun")
    vehicle_assignments = relationship(
        "VehicleAssignment",
        back_populates="dispatch_plan",
        cascade="all, delete-orphan",
        order_by="VehicleAssignment.id",
    )


class VehicleAssignment(Base, TimestampMixin):
    """Single vehicle tour originating from and returning to its home warehouse depot."""

    __tablename__ = "vehicle_assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dispatch_plan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dispatch_plans.id", ondelete="CASCADE"), index=True, nullable=False
    )
    vehicle_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicles.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    warehouse_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    trip_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="planned"
    )
    total_load_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    capacity_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    utilization_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    route_distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_duration_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    route_coordinates_json: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    route_geometry_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, default=None)
    assigned_driver_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    preparation_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True, default="pending"
    )  # pending | preparing | ready_for_dispatch | handed_over
    preparation_notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    dispatch_plan = relationship("DispatchPlan", back_populates="vehicle_assignments")
    vehicle = relationship("Vehicle")
    warehouse = relationship("Warehouse")
    assigned_driver = relationship("User")
    delivery_stops = relationship(
        "DeliveryStop",
        back_populates="vehicle_assignment",
        cascade="all, delete-orphan",
        order_by="DeliveryStop.stop_sequence",
    )


class DeliveryStop(Base, TimestampMixin):
    """Ordered hospital delivery stop inside a vehicle assignment tour."""

    __tablename__ = "delivery_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_assignment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vehicle_assignments.id", ondelete="CASCADE"), index=True, nullable=False
    )
    hospital_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("hospitals.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), index=True, nullable=False, default="planned"
    )
    leg_distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cumulative_distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    estimated_arrival_min: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    stop_weight_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_by_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    vehicle_assignment = relationship("VehicleAssignment", back_populates="delivery_stops")
    hospital = relationship("Hospital")
    shipment_lines = relationship(
        "ShipmentLine",
        back_populates="delivery_stop",
        cascade="all, delete-orphan",
        order_by="ShipmentLine.id",
    )


class ShipmentLine(Base, TimestampMixin):
    """Product-level medical supply quantities planned and delivered at a hospital stop."""

    __tablename__ = "shipment_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_stop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("delivery_stops.id", ondelete="CASCADE"), index=True, nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    quantity_planned: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    quantity_delivered: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit_weight_kg: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    total_weight_kg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Relationships
    delivery_stop = relationship("DeliveryStop", back_populates="shipment_lines")
    product = relationship("Product")
