"""API integration tests for MEDILOGIX FastAPI backend."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.connection import get_db
from app.main import app


def _create_test_client() -> TestClient:
    """Create a FastAPI TestClient backed by an isolated in-memory SQLite DB."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_health_endpoint() -> None:
    client = _create_test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "MEDILOGIX API"
    assert "geographical_scope" in payload
    assert payload["geographical_scope"]["region_name"] == "Pune Urban & Pimpri-Chinchwad"


def test_warehouse_crud_lifecycle() -> None:
    client = _create_test_client()

    create_payload = {
        "code": "WH-TEST-01",
        "name": "Test Simulation Depot",
        "area": "Aundh",
        "city": "Pune",
        "latitude": 18.559,
        "longitude": 73.8077,
        "storage_capacity_units": 1500,
        "status": "active",
        "is_synthetic_hub": True,
    }
    create_res = client.post("/api/warehouses", json=create_payload)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["code"] == "WH-TEST-01"

    list_res = client.get("/api/warehouses")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    update_res = client.put(
        f"/api/warehouses/{created['id']}", json={"storage_capacity_units": 2000}
    )
    assert update_res.status_code == 200
    assert update_res.json()["storage_capacity_units"] == 2000

    delete_res = client.delete(f"/api/warehouses/{created['id']}")
    assert delete_res.status_code == 204


def test_analytics_summary_empty_db() -> None:
    client = _create_test_client()
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_warehouses"] == 0
    assert data["latest_distribution_cost"] is None
    assert data["latest_demand_fulfillment_pct"] is None
