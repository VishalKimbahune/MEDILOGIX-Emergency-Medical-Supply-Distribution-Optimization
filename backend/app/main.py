"""
MEDILOGIX FastAPI Application Entrypoint.

Exposes modular REST APIs for emergency medical supply chain data,
Operations Research solvers, routing, disaster scenarios, and analytics.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin,
    analytics,
    auth,
    delivery_portal,
    demands,
    hospital_portal,
    hospitals,
    inventory,
    notifications,
    optimization,
    products,
    routes,
    scenarios,
    warehouse_portal,
    warehouses,
)
from app.core.config import get_settings
from app.database.base import Base
from app.database.connection import check_database_connection, engine
from app.database.migrations import ensure_additive_columns
from app import models as _models  # noqa: F401 - ensure all tables are registered

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Non-destructively ensure any newly added ORM tables and additive columns exist on startup."""
    Base.metadata.create_all(bind=engine)
    ensure_additive_columns(engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    description=(
        "Emergency Medical Supply Distribution Optimization Using Operations Research "
        "and Intelligent Decision Support (Pune & Pimpri-Chinchwad Simulation Scope)."
    ),
)

# Enable CORS for local React development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register modular routers
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(hospital_portal.router)
app.include_router(warehouse_portal.router)
app.include_router(delivery_portal.router)
app.include_router(notifications.router)
app.include_router(warehouses.router)
app.include_router(hospitals.router)
app.include_router(products.router)
app.include_router(inventory.router)
app.include_router(demands.router)
app.include_router(optimization.router)
app.include_router(routes.router)
app.include_router(scenarios.router)
app.include_router(analytics.router)


@app.get("/", tags=["System"])
def root() -> dict[str, str]:
    """Root welcome endpoint pointing to health and Swagger docs."""
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "health": "/api/health",
        "docs": "/docs",
    }


@app.get("/api/health", tags=["System"])
def health_check() -> dict[str, Any]:
    """System health check endpoint reporting API and database readiness."""
    db_ok = check_database_connection()
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "database_connected": db_ok,
        "geographical_scope": {
            "region_name": settings.geo_region_name,
            "bounds": {
                "min_lat": settings.geo_min_lat,
                "max_lat": settings.geo_max_lat,
                "min_lon": settings.geo_min_lon,
                "max_lon": settings.geo_max_lon,
            },
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
