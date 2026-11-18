"""
MEDILOGIX FastAPI Application Entrypoint.

Exposes modular REST APIs for emergency medical supply chain data,
Operations Research solvers, routing, disaster scenarios, and analytics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    analytics,
    demands,
    hospitals,
    inventory,
    optimization,
    products,
    routes,
    scenarios,
    warehouses,
)
from app.core.config import get_settings
from app.database.connection import check_database_connection

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
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
