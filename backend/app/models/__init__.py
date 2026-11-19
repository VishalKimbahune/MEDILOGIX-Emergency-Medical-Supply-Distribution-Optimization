"""Export all SQLAlchemy ORM models for unified metadata registration."""

from app.models.allocation import Allocation
from app.models.delivery import Delivery
from app.models.demand import Demand
from app.models.dispatch import DeliveryStop, DispatchPlan, ShipmentLine, VehicleAssignment
from app.models.hospital import Hospital
from app.models.inventory import Inventory
from app.models.optimization_run import OptimizationRun
from app.models.platform import AuditLog, Notification, StockMovement
from app.models.product import Product
from app.models.road import Road
from app.models.scenario import Scenario
from app.models.scenario_run import ScenarioRun
from app.models.user import (
    EmailVerificationToken,
    PasswordResetToken,
    RefreshToken,
    User,
)
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse

__all__ = [
    "Warehouse",
    "Hospital",
    "Product",
    "Inventory",
    "Demand",
    "Road",
    "Vehicle",
    "Scenario",
    "ScenarioRun",
    "OptimizationRun",
    "Allocation",
    "Delivery",
    "DispatchPlan",
    "VehicleAssignment",
    "DeliveryStop",
    "ShipmentLine",
    "User",
    "RefreshToken",
    "PasswordResetToken",
    "EmailVerificationToken",
    "Notification",
    "AuditLog",
    "StockMovement",
]
