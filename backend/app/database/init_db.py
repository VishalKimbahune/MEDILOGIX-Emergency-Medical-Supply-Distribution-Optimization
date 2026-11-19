"""
Database schema initialization and idempotent synthetic seed runner.

Usage (from backend/):
    python -m app.database.init_db
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings
from app.database.base import Base
from app.database.connection import SessionLocal, engine
from app.database.migrations import ensure_additive_columns
from app.models import (  # noqa: F401 - ensure all ORM models register with Base.metadata
    Allocation,
    Delivery,
    DeliveryStop,
    Demand,
    DispatchPlan,
    Hospital,
    Inventory,
    OptimizationRun,
    Product,
    Road,
    Scenario,
    ScenarioRun,
    ShipmentLine,
    Vehicle,
    VehicleAssignment,
    Warehouse,
)
from app.utils.dataset_loader import seed_database_from_csv

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def init_db(seed: bool = True) -> dict[str, int]:
    """Create all tables and optionally load initial synthetic CSV data."""
    Base.metadata.create_all(bind=engine)
    ensure_additive_columns(engine)
    logger.info("Database schema initialized successfully.")

    if not seed:
        return {}

    settings = get_settings()
    data_dir = Path(settings.synthetic_data_dir)
    if not data_dir.is_absolute():
        data_dir = (Path(__file__).resolve().parents[2] / data_dir).resolve()

    if not data_dir.exists():
        logger.warning(
            "Synthetic dataset directory not found at %s. Run 'python data/generate_dataset.py' first.",
            data_dir,
        )
        return {}

    with SessionLocal() as session:
        counts = seed_database_from_csv(session, data_dir)
        logger.info("Seed summary: %s", counts)
        return counts


if __name__ == "__main__":
    init_db(seed=True)
