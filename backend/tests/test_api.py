"""API integration tests for MEDILOGIX FastAPI backend."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.connection import get_db
from app.main import app


def _create_test_client() -> TestClient:
    """Create a FastAPI TestClient backed by an isolated in-memory SQLite DB with FK checks."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_sqlite_fks(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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


def _seed_base_entities(client: TestClient) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Helper to create one warehouse, one hospital, and one medical product."""
    wh = client.post(
        "/api/warehouses",
        json={
            "code": "WH-T1",
            "name": "Baner Emergency Hub (Simulation)",
            "area": "Baner",
            "city": "Pune",
            "latitude": 18.559,
            "longitude": 73.7868,
            "storage_capacity_units": 3000,
            "status": "active",
            "is_synthetic_hub": True,
        },
    ).json()
    hosp = client.post(
        "/api/hospitals",
        json={
            "code": "HOSP-T1",
            "name": "Kothrud Civic Hospital (Synthetic)",
            "area": "Kothrud",
            "city": "Pune",
            "latitude": 18.5074,
            "longitude": 73.8077,
            "priority_level": "high",
            "bed_capacity": 240,
            "status": "active",
            "is_synthetic_profile": True,
        },
    ).json()
    prod = client.post(
        "/api/products",
        json={
            "code": "PROD-T1",
            "name": "Oxygen Cylinders",
            "category": "Respiratory Support",
            "unit": "cylinder",
            "unit_weight_kg": 18.5,
            "base_transport_cost_per_km": 4.5,
            "cold_chain_required": False,
        },
    ).json()
    return wh, hosp, prod


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

    # Duplicate code rejected
    dup_res = client.post("/api/warehouses", json=create_payload)
    assert dup_res.status_code == 409

    list_res = client.get("/api/warehouses")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    update_res = client.put(
        f"/api/warehouses/{created['id']}",
        json={"storage_capacity_units": 2000, "status": "maintenance"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["storage_capacity_units"] == 2000
    assert update_res.json()["status"] == "maintenance"

    delete_res = client.delete(f"/api/warehouses/{created['id']}")
    assert delete_res.status_code == 204
    assert client.get(f"/api/warehouses/{created['id']}").status_code == 404


def test_hospital_crud_priority_and_filters() -> None:
    client = _create_test_client()

    create_res = client.post(
        "/api/hospitals",
        json={
            "code": "HOSP-TEST-01",
            "name": "Shivajinagar Emergency Unit (Synthetic)",
            "area": "Shivajinagar",
            "city": "Pune",
            "latitude": 18.5308,
            "longitude": 73.8475,
            "priority_level": "normal",
            "bed_capacity": 180,
            "status": "active",
            "is_synthetic_profile": True,
        },
    )
    assert create_res.status_code == 201
    hosp = create_res.json()

    # Escalate emergency priority from normal -> critical
    update_res = client.put(
        f"/api/hospitals/{hosp['id']}",
        json={"priority_level": "critical", "bed_capacity": 320},
    )
    assert update_res.status_code == 200
    assert update_res.json()["priority_level"] == "critical"
    assert update_res.json()["bed_capacity"] == 320

    # Filter by priority and locality
    filtered = client.get("/api/hospitals", params={"priority_level": "critical", "area": "Shivaji"})
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1

    # Delete hospital without dependent records
    del_res = client.delete(f"/api/hospitals/{hosp['id']}")
    assert del_res.status_code == 204


def test_inventory_crud_validation_and_fk_protection() -> None:
    client = _create_test_client()
    wh, _hosp, prod = _seed_base_entities(client)

    # Create inventory
    create_res = client.post(
        "/api/inventory",
        json={
            "inventory_code": "INV-T01",
            "warehouse_id": wh["id"],
            "product_id": prod["id"],
            "quantity_available": 140,
            "quantity_reserved": 10,
            "reorder_level": 30,
            "data_note": "Initial synthetic stock",
        },
    )
    assert create_res.status_code == 201
    inv = create_res.json()
    assert inv["quantity_available"] == 140

    # Update stock
    update_res = client.put(
        f"/api/inventory/{inv['id']}",
        json={"quantity_available": 25, "quantity_reserved": 5, "reorder_level": 30},
    )
    assert update_res.status_code == 200
    assert update_res.json()["quantity_available"] == 25

    # Reject reserved > available on update
    invalid_res = client.put(
        f"/api/inventory/{inv['id']}",
        json={"quantity_available": 10, "quantity_reserved": 15},
    )
    assert invalid_res.status_code == 422

    # Reject negative stock quantities
    neg_create = client.post(
        "/api/inventory",
        json={
            "inventory_code": "INV-NEG",
            "warehouse_id": wh["id"],
            "product_id": prod["id"],
            "quantity_available": -5,
            "quantity_reserved": 0,
            "reorder_level": 10,
        },
    )
    assert neg_create.status_code == 422

    neg_update = client.put(f"/api/inventory/{inv['id']}", json={"quantity_available": -1})
    assert neg_update.status_code == 422

    # Foreign-key validation: non-existent warehouse or product
    bad_wh_fk = client.post(
        "/api/inventory",
        json={
            "inventory_code": "INV-BAD-WH",
            "warehouse_id": 99999,
            "product_id": prod["id"],
            "quantity_available": 50,
            "quantity_reserved": 0,
            "reorder_level": 10,
        },
    )
    assert bad_wh_fk.status_code == 404

    # Prevent deleting warehouse while inventory references it
    blocked_wh_del = client.delete(f"/api/warehouses/{wh['id']}")
    assert blocked_wh_del.status_code == 409
    assert "inventory" in blocked_wh_del.json()["detail"].lower()

    # After removing dependent inventory, warehouse deletion succeeds
    assert client.delete(f"/api/inventory/{inv['id']}").status_code == 204
    assert client.delete(f"/api/warehouses/{wh['id']}").status_code == 204


def test_demand_crud_filtering_validation_and_fk_protection() -> None:
    client = _create_test_client()
    _wh, hosp, prod = _seed_base_entities(client)

    # Create demand request
    create_res = client.post(
        "/api/demands",
        json={
            "demand_code": "DEM-T01",
            "hospital_id": hosp["id"],
            "product_id": prod["id"],
            "quantity_requested": 85,
            "priority_level": "high",
            "status": "open",
            "data_note": "Respiratory surge",
        },
    )
    assert create_res.status_code == 201
    dem = create_res.json()
    assert dem["quantity_requested"] == 85

    # Filter demands by hospital, product, priority, and status
    filtered = client.get(
        "/api/demands",
        params={
            "hospital_id": hosp["id"],
            "product_id": prod["id"],
            "priority_level": "high",
            "status": "open",
        },
    )
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1

    # Update quantity and valid status
    update_res = client.put(
        f"/api/demands/{dem['id']}",
        json={
            "quantity_requested": 110,
            "priority_level": "critical",
            "status": "partially_fulfilled",
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["quantity_requested"] == 110
    assert update_res.json()["status"] == "partially_fulfilled"

    # Reject negative and zero demand quantities
    neg_dem = client.post(
        "/api/demands",
        json={
            "demand_code": "DEM-NEG",
            "hospital_id": hosp["id"],
            "product_id": prod["id"],
            "quantity_requested": -10,
            "priority_level": "high",
            "status": "open",
        },
    )
    assert neg_dem.status_code == 422

    zero_dem_update = client.put(f"/api/demands/{dem['id']}", json={"quantity_requested": 0})
    assert zero_dem_update.status_code == 422

    # Reject unsupported status
    bad_status = client.put(f"/api/demands/{dem['id']}", json={"status": "unknown_status"})
    assert bad_status.status_code == 422

    # Foreign-key check on non-existent hospital
    bad_hosp_fk = client.post(
        "/api/demands",
        json={
            "demand_code": "DEM-BAD-HOSP",
            "hospital_id": 99999,
            "product_id": prod["id"],
            "quantity_requested": 20,
            "priority_level": "normal",
            "status": "open",
        },
    )
    assert bad_hosp_fk.status_code == 404

    # Prevent deleting hospital while demand references it
    blocked_hosp_del = client.delete(f"/api/hospitals/{hosp['id']}")
    assert blocked_hosp_del.status_code == 409
    assert "demands" in blocked_hosp_del.json()["detail"].lower()

    # Delete demand then delete hospital
    assert client.delete(f"/api/demands/{dem['id']}").status_code == 204
    assert client.delete(f"/api/hospitals/{hosp['id']}").status_code == 204


def test_invalid_inputs_and_nonexistent_ids() -> None:
    client = _create_test_client()

    # Non-existent IDs return 404 across all 4 modules
    assert client.get("/api/warehouses/99999").status_code == 404
    assert client.put("/api/warehouses/99999", json={"name": "Nope"}).status_code == 404
    assert client.delete("/api/warehouses/99999").status_code == 404

    assert client.get("/api/hospitals/99999").status_code == 404
    assert client.put("/api/hospitals/99999", json={"priority_level": "critical"}).status_code == 404
    assert client.delete("/api/hospitals/99999").status_code == 404

    assert client.get("/api/inventory/99999").status_code == 404
    assert client.put("/api/inventory/99999", json={"quantity_available": 50}).status_code == 404
    assert client.delete("/api/inventory/99999").status_code == 404

    assert client.get("/api/demands/99999").status_code == 404
    assert client.put("/api/demands/99999", json={"status": "fulfilled"}).status_code == 404
    assert client.delete("/api/demands/99999").status_code == 404

    # Invalid coordinates & capacity rejected with 422
    bad_wh = client.post(
        "/api/warehouses",
        json={
            "code": "WH-BAD",
            "name": "Bad Coords Depot",
            "area": "Pune",
            "city": "Pune",
            "latitude": 120.5,
            "longitude": 73.85,
            "storage_capacity_units": 0,
            "status": "active",
        },
    )
    assert bad_wh.status_code == 422


def test_analytics_summary_and_latest_allocations_empty_db() -> None:
    client = _create_test_client()
    res = client.get("/api/analytics/summary")
    assert res.status_code == 200
    data = res.json()
    assert data["total_warehouses"] == 0
    assert data["latest_distribution_cost"] is None
    assert data["latest_demand_fulfillment_pct"] is None

    latest_allocs = client.get("/api/optimization/latest-allocations")
    assert latest_allocs.status_code == 200
    assert latest_allocs.json()["run_code"] is None
    assert latest_allocs.json()["allocations_by_pair"] == {}
