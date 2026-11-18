"""Export all SQLAlchemy ORM models for unified metadata registration."""

from app.models.allocation import Allocation
from app.models.delivery import Delivery
from app.models.demand import Demand
from app.models.hospital import Hospital
from app.models.inventory import Inventory
from app.models.optimization_run import OptimizationRun
from app.models.product import Product
from app.models.road import Road
from app.models.scenario import Scenario
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
    "OptimizationRun",
    "Allocation",
    "Delivery",
]
