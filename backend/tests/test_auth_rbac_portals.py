"""
Comprehensive Security, Authentication, RBAC, Cross-Organization Isolation,
and Full 10-Step End-to-End 4-Portal Workflow Tests.

Runs completely deterministically against isolated in-memory SQLite databases
seeded from synthetic CSVs and mocked OSM road graphs — never touches medilogix_dev.db.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import auth_rate_limiter, hash_password, verify_password
from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.models.demand import Demand
from app.models.hospital import Hospital
from app.models.inventory import Inventory
from app.models.platform import AuditLog, StockMovement
from app.models.product import Product
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.warehouse import Warehouse
from app.optimization.osm_road_network import save_graph_cache
from app.services import road_network_service
from app.utils.dataset_loader import seed_database_from_csv
from tests.test_phase5b_osm_vrp_integration import _build_mock_pune_osm_graph

SYNTHETIC_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def _create_isolated_env() -> tuple[TestClient, Any]:
    """Create isolated seeded in-memory DB + fresh TestClient with rate limiter cleared."""
    auth_rate_limiter.clear()
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_fks(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with TestingSessionLocal() as db:
        seed_database_from_csv(db, SYNTHETIC_DATA_DIR)
        admin = User(
            full_name="Primary System Admin",
            email="admin@medilogix.org",
            hashed_password=hash_password("AdminStrong!2026"),
            role="admin",
            is_active=True,
            is_verified=True,
            is_approved=True,
            approval_status="approved",
        )
        db.add(admin)
        db.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app), TestingSessionLocal


def _login_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. AUTHENTICATION, REGISTRATION, REFRESH, PASSWORD RESET & RATE LIMITING
# =============================================================================


def test_registration_security_approval_and_argon2_hashing() -> None:
    client, SessionLocal = _create_isolated_env()

    # Public organizations endpoint works without auth
    orgs_res = client.get("/api/auth/public-organizations")
    assert orgs_res.status_code == 200
    orgs = orgs_res.json()
    assert len(orgs["hospitals"]) == 8
    assert len(orgs["warehouses"]) == 3
    hosp1_id = orgs["hospitals"][0]["id"]

    # Public registration NEVER allows admin role (422)
    bad_admin = client.post(
        "/api/auth/register",
        json={
            "full_name": "Rogue Admin",
            "email": "rogue@medilogix.org",
            "password": "Password!123",
            "confirm_password": "Password!123",
            "role": "admin",
        },
    )
    assert bad_admin.status_code == 422

    # Valid hospital registration starts pending approval
    reg_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Dr. Meera Kulkarni",
            "email": "meera@hosp1.org",
            "password": "HospitalPass!2026",
            "confirm_password": "HospitalPass!2026",
            "phone_number": "+91-9822001122",
            "role": "hospital",
            "associated_hospital_id": hosp1_id,
        },
    )
    assert reg_res.status_code == 201, reg_res.text
    reg_data = reg_res.json()
    assert reg_data["user"]["approval_status"] == "pending"
    assert reg_data["user"]["is_approved"] is False
    user_id = reg_data["user"]["id"]

    # Verify Argon2id hash stored in DB (never plaintext)
    with SessionLocal() as db:
        u = db.get(User, user_id)
        assert u is not None
        assert u.hashed_password.startswith("$argon2")
        assert u.hashed_password != "HospitalPass!2026"
        assert verify_password("HospitalPass!2026", u.hashed_password)

    # Duplicate email returns 409
    dup_res = client.post(
        "/api/auth/register",
        json={
            "full_name": "Duplicate",
            "email": "meera@hosp1.org",
            "password": "HospitalPass!2026",
            "confirm_password": "HospitalPass!2026",
            "role": "hospital",
            "associated_hospital_id": hosp1_id,
        },
    )
    assert dup_res.status_code == 409

    # Pending user CANNOT log in (403)
    pending_login = client.post(
        "/api/auth/login",
        json={"email": "meera@hosp1.org", "password": "HospitalPass!2026"},
    )
    assert pending_login.status_code == 403
    assert "pending" in pending_login.json()["detail"].lower()

    # Email verification works with dev link
    verify_url = reg_data.get("dev_verify_url")
    assert verify_url and "token=" in verify_url
    verify_token = verify_url.split("token=")[-1]
    verify_res = client.post("/api/auth/verify-email", json={"token": verify_token})
    assert verify_res.status_code == 200

    # Admin approves user
    admin_hdrs = _login_headers(client, "admin@medilogix.org", "AdminStrong!2026")
    approve_res = client.patch(f"/api/admin/users/{user_id}/approve", headers=admin_hdrs)
    assert approve_res.status_code == 200
    assert approve_res.json()["approval_status"] == "approved"

    # Now hospital user CAN log in
    hosp_login = client.post(
        "/api/auth/login",
        json={"email": "meera@hosp1.org", "password": "HospitalPass!2026"},
    )
    assert hosp_login.status_code == 200
    assert hosp_login.json()["user"]["role"] == "hospital"
    assert "medilogix_refresh_token" in hosp_login.cookies


def test_refresh_rotation_logout_password_reset_and_rate_limit() -> None:
    client, SessionLocal = _create_isolated_env()

    # Login sets HTTP-only refresh cookie
    login_res = client.post(
        "/api/auth/login",
        json={"email": "admin@medilogix.org", "password": "AdminStrong!2026"},
    )
    assert login_res.status_code == 200
    old_cookie = login_res.cookies.get("medilogix_refresh_token")
    assert old_cookie

    # Refresh rotates token (requires X-Requested-With header CSRF guard)
    ref_res = client.post(
        "/api/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert ref_res.status_code == 200, ref_res.text
    new_cookie = ref_res.cookies.get("medilogix_refresh_token")
    assert new_cookie and new_cookie != old_cookie

    # Logout revokes refresh session
    out_res = client.post("/api/auth/logout")
    assert out_res.status_code == 200
    # Refresh after logout must fail with 401
    after_out = client.post(
        "/api/auth/refresh",
        headers={"X-Requested-With": "XMLHttpRequest"},
    )
    assert after_out.status_code == 401

    # Forgot password + Reset password (single-use)
    forgot_res = client.post("/api/auth/forgot-password", json={"email": "admin@medilogix.org"})
    assert forgot_res.status_code == 200
    reset_url = forgot_res.json().get("dev_reset_url")
    assert reset_url and "token=" in reset_url
    reset_token = reset_url.split("token=")[-1]

    reset_res = client.post(
        "/api/auth/reset-password",
        json={
            "token": reset_token,
            "new_password": "NewAdminStrong!2026",
            "confirm_password": "NewAdminStrong!2026",
        },
    )
    assert reset_res.status_code == 200

    # Reusing same token fails (400)
    reuse_res = client.post(
        "/api/auth/reset-password",
        json={
            "token": reset_token,
            "new_password": "AnotherStrong!2026",
            "confirm_password": "AnotherStrong!2026",
        },
    )
    assert reuse_res.status_code == 400

    # Old password fails, new password succeeds
    old_login = client.post(
        "/api/auth/login",
        json={"email": "admin@medilogix.org", "password": "AdminStrong!2026"},
    )
    assert old_login.status_code == 401
    new_login = client.post(
        "/api/auth/login",
        json={"email": "admin@medilogix.org", "password": "NewAdminStrong!2026"},
    )
    assert new_login.status_code == 200

    # Verify audit logs contain ZERO plaintext passwords or tokens
    with SessionLocal() as db:
        logs = db.scalars(select(AuditLog)).all()
        for lg in logs:
            raw_meta = str(lg.metadata_json or "")
            assert "AdminStrong!2026" not in raw_meta
            assert "NewAdminStrong!2026" not in raw_meta
            assert reset_token not in raw_meta

    # Login rate limiting triggers 429 after excessive attempts
    auth_rate_limiter.clear()
    statuses = []
    for _ in range(12):
        r = client.post(
            "/api/auth/login",
            json={"email": "ratelimit@medilogix.org", "password": "WrongPassword!1"},
        )
        statuses.append(r.status_code)
    assert 429 in statuses


def test_last_active_admin_cannot_be_deactivated_or_demoted() -> None:
    client, SessionLocal = _create_isolated_env()
    admin_hdrs = _login_headers(client, "admin@medilogix.org", "AdminStrong!2026")

    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == "admin@medilogix.org"))
        assert admin is not None
        admin_id = admin.id

    deact = client.patch(
        f"/api/admin/users/{admin_id}/status",
        headers=admin_hdrs,
        json={"is_active": False},
    )
    assert deact.status_code == 400
    assert "last active admin" in deact.json()["detail"].lower()

    demote = client.patch(
        f"/api/admin/users/{admin_id}",
        headers=admin_hdrs,
        json={"role": "delivery"},
    )
    assert demote.status_code == 400


# =============================================================================
# 2. STRICT RBAC & CROSS-ORGANIZATION ISOLATION
# =============================================================================


def test_rbac_and_cross_organization_isolation() -> None:
    client, SessionLocal = _create_isolated_env()

    # Unauthenticated access to protected endpoints returns 401
    for path in [
        "/api/warehouses",
        "/api/hospitals",
        "/api/inventory",
        "/api/demands",
        "/api/optimization/runs",
        "/api/routes/dispatch-plans",
        "/api/analytics/summary",
        "/api/admin/users",
        "/api/hospital/dashboard",
        "/api/warehouse/dashboard",
        "/api/delivery/dashboard",
        "/api/notifications",
    ]:
        assert client.get(path).status_code == 401, f"Expected 401 for {path}"

    # Seed 2 hospitals users, 2 warehouse users, 2 delivery users
    with SessionLocal() as db:
        hosps = list(db.scalars(select(Hospital).order_by(Hospital.code)).all())
        whs = list(db.scalars(select(Warehouse).order_by(Warehouse.code)).all())
        prods = list(db.scalars(select(Product).order_by(Product.code)).all())
        h1, h2 = hosps[0], hosps[1]
        w1, w2 = whs[0], whs[1]
        p1 = prods[0]

        for email, role, hid, wid in [
            ("h1@test.org", "hospital", h1.id, None),
            ("h2@test.org", "hospital", h2.id, None),
            ("w1@test.org", "warehouse", None, w1.id),
            ("w2@test.org", "warehouse", None, w2.id),
            ("d1@test.org", "delivery", None, None),
            ("d2@test.org", "delivery", None, None),
        ]:
            db.add(
                User(
                    full_name=email,
                    email=email,
                    hashed_password=hash_password("UserPass!2026"),
                    role=role,
                    is_active=True,
                    is_verified=True,
                    is_approved=True,
                    approval_status="approved",
                    associated_hospital_id=hid,
                    associated_warehouse_id=wid,
                )
            )
        db.commit()
        w2_inv = db.scalar(select(Inventory).where(Inventory.warehouse_id == w2.id))
        assert w2_inv is not None
        w2_inv_id = w2_inv.id
        p1_id = p1.id

    h1_hdrs = _login_headers(client, "h1@test.org", "UserPass!2026")
    h2_hdrs = _login_headers(client, "h2@test.org", "UserPass!2026")
    w1_hdrs = _login_headers(client, "w1@test.org", "UserPass!2026")
    d1_hdrs = _login_headers(client, "d1@test.org", "UserPass!2026")

    # Cross-portal forbidden checks (403)
    assert client.get("/api/admin/users", headers=h1_hdrs).status_code == 403
    assert client.get("/api/warehouse/dashboard", headers=h1_hdrs).status_code == 403
    assert client.get("/api/delivery/dashboard", headers=h1_hdrs).status_code == 403
    assert client.get("/api/optimization/runs", headers=h1_hdrs).status_code == 403
    assert client.get("/api/inventory", headers=h1_hdrs).status_code == 403
    assert client.get("/api/hospital/dashboard", headers=w1_hdrs).status_code == 403
    assert client.get("/api/delivery/dashboard", headers=w1_hdrs).status_code == 403
    assert client.get("/api/hospital/dashboard", headers=d1_hdrs).status_code == 403
    assert client.get("/api/warehouse/dashboard", headers=d1_hdrs).status_code == 403

    # Hospital 1 creates order -> Hospital 2 CANNOT read it (403)
    ord_res = client.post(
        "/api/hospital/orders",
        headers=h1_hdrs,
        json={
            "priority_level": "critical",
            "emergency_reason": "ICU surge",
            "items": [{"product_id": p1_id, "quantity_requested": 45}],
        },
    )
    assert ord_res.status_code == 201, ord_res.text
    order_id = ord_res.json()["orders"][0]["id"]
    assert ord_res.json()["orders"][0]["status"] == "pending_approval"

    assert client.get(f"/api/hospital/orders/{order_id}", headers=h1_hdrs).status_code == 200
    assert client.get(f"/api/hospital/orders/{order_id}", headers=h2_hdrs).status_code == 403

    # Warehouse 1 CANNOT adjust Warehouse 2's inventory (403)
    bad_stock = client.patch(
        f"/api/warehouse/inventory/{w2_inv_id}",
        headers=w1_hdrs,
        json={"movement_type": "stock_in", "quantity_delta": 25, "reason": "Unauthorized attempt"},
    )
    assert bad_stock.status_code == 403


# =============================================================================
# 3. WAREHOUSE STATUS, STOCK MOVEMENT & OPTIMIZATION EXCLUSION
# =============================================================================


def test_warehouse_status_and_stock_movements_affect_optimization() -> None:
    client, SessionLocal = _create_isolated_env()

    with SessionLocal() as db:
        wh1 = db.scalar(select(Warehouse).where(Warehouse.code == "WH-01"))
        assert wh1 is not None
        wh1_id = wh1.id
        inv1 = db.scalar(select(Inventory).where(Inventory.warehouse_id == wh1.id))
        assert inv1 is not None
        inv1_id = inv1.id
        orig_qty = inv1.quantity_available

        db.add(
            User(
                full_name="WH-01 Manager",
                email="wh1.mgr@test.org",
                hashed_password=hash_password("WarePass!2026"),
                role="warehouse",
                is_active=True,
                is_verified=True,
                is_approved=True,
                approval_status="approved",
                associated_warehouse_id=wh1_id,
            )
        )
        db.commit()

    wh_hdrs = _login_headers(client, "wh1.mgr@test.org", "WarePass!2026")
    admin_hdrs = _login_headers(client, "admin@medilogix.org", "AdminStrong!2026")

    # Stock-in increases inventory and records StockMovement
    in_res = client.patch(
        f"/api/warehouse/inventory/{inv1_id}",
        headers=wh_hdrs,
        json={"movement_type": "stock_in", "quantity_delta": 50, "reason": "Emergency restock truck"},
    )
    assert in_res.status_code == 200
    assert in_res.json()["quantity_available"] == orig_qty + 50

    # Negative resulting stock is blocked (422)
    neg_res = client.patch(
        f"/api/warehouse/inventory/{inv1_id}",
        headers=wh_hdrs,
        json={"movement_type": "adjustment", "quantity_delta": -999999, "reason": "Invalid negative"},
    )
    assert neg_res.status_code == 422

    # Movement history recorded
    mov_res = client.get("/api/warehouse/stock-movements", headers=wh_hdrs)
    assert mov_res.status_code == 200
    assert any(m["quantity_delta"] == 50 for m in mov_res.json())

    # Warehouse can also add a brand-new medicine + initial stock directly
    new_med_res = client.post(
        "/api/warehouse/products-with-stock",
        headers=wh_hdrs,
        json={
            "name": "Insulin Cold-Chain Vials",
            "category": "cold_chain",
            "unit": "vial",
            "unit_weight_kg": 0.5,
            "quantity_available": 200,
            "reorder_level": 40,
        },
    )
    assert new_med_res.status_code == 201, new_med_res.text
    assert new_med_res.json()["product"]["code"] == "PROD-05"
    assert new_med_res.json()["inventory"]["quantity_available"] == 200

    # Set WH-01 to maintenance -> excluded from new optimization while stock stays preserved
    st_res = client.patch(
        "/api/warehouse/status",
        headers=wh_hdrs,
        json={"status": "maintenance", "reason": "Cold-chain compressor inspection"},
    )
    assert st_res.status_code == 200
    assert st_res.json()["status"] == "maintenance"

    opt_res = client.post("/api/optimization/priority", headers=admin_hdrs, json={})
    assert opt_res.status_code == 200
    opt_data = opt_res.json()
    assert all(a["warehouse_code"] != "WH-01" for a in opt_data["allocations"])

    # Stock is preserved in DB
    with SessionLocal() as db:
        refreshed_inv = db.get(Inventory, inv1_id)
        assert refreshed_inv is not None
        assert refreshed_inv.quantity_available == orig_qty + 50


# =============================================================================
# 4. FULL 10-STEP END-TO-END 4-PORTAL WORKFLOW TEST
# =============================================================================


def test_full_10_step_end_to_end_multi_portal_workflow(tmp_path: Path, monkeypatch) -> None:
    """
    1. Hospital registers -> Pending
    2. Admin approves Hospital, Warehouse & Delivery users + assigns vehicle to driver
    3. Hospital submits multi-product emergency order -> stays `pending_approval` (excluded from LP)
    4. Admin approves order -> enters LP
    5. Admin executes Lexicographic Priority Optimization
    6. Admin generates OR-Tools OSM Dispatch Plan
    7. Warehouse marks shipment preparation -> ready_for_dispatch
    8. Delivery driver views assigned OSM route -> marks dispatched/in_transit -> confirms partial then full delivery
       (and another driver is blocked with 403; over-delivery blocked with 422; re-confirmation blocked with 409)
    9. Hospital tracks updated visual timeline showing Delivered status
    10. Admin inspects Analytics & append-only Audit Logs
    """
    client, SessionLocal = _create_isolated_env()

    # Use deterministic mocked Pune OSM graph cache
    cache_path = tmp_path / "mock_pune_osm.json"
    save_graph_cache(
        _build_mock_pune_osm_graph(),
        cache_path,
        bbox={"min_lat": 18.4, "max_lat": 18.7, "min_lon": 73.7, "max_lon": 74.0},
    )
    road_network_service.clear_memory_cache()
    monkeypatch.setattr(
        road_network_service,
        "_resolve_cache_path",
        lambda override_path=None: override_path or cache_path,
    )

    admin_hdrs = _login_headers(client, "admin@medilogix.org", "AdminStrong!2026")

    with SessionLocal() as db:
        hosp1 = db.scalar(select(Hospital).where(Hospital.code == "HOSP-01"))
        wh1 = db.scalar(select(Warehouse).where(Warehouse.code == "WH-01"))
        prods = list(db.scalars(select(Product).order_by(Product.code)).all())
        vehicles = list(db.scalars(select(Vehicle).order_by(Vehicle.vehicle_code)).all())
        assert hosp1 and wh1 and len(prods) >= 2 and vehicles
        hosp1_id, wh1_id = hosp1.id, wh1.id
        p1_id, p2_id = prods[0].id, prods[1].id
        veh_ids = [v.id for v in vehicles]

    # Step 1: Hospital, Warehouse, Delivery & Second Driver register publicly
    h_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Sassoon Emergency Coordinator",
            "email": "sassoon@hosp.org",
            "password": "HospStrong!2026",
            "confirm_password": "HospStrong!2026",
            "role": "hospital",
            "associated_hospital_id": hosp1_id,
        },
    ).json()["user"]
    w_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Pimpri Hub Manager",
            "email": "pimpri@wh.org",
            "password": "WhStrong!2026",
            "confirm_password": "WhStrong!2026",
            "role": "warehouse",
            "associated_warehouse_id": wh1_id,
        },
    ).json()["user"]
    d_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Rohan Deshmukh",
            "email": "rohan@delivery.org",
            "password": "DelivStrong!2026",
            "confirm_password": "DelivStrong!2026",
            "role": "delivery",
        },
    ).json()["user"]
    other_d_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Other Driver",
            "email": "other@delivery.org",
            "password": "DelivStrong!2026",
            "confirm_password": "DelivStrong!2026",
            "role": "delivery",
        },
    ).json()["user"]

    # Step 2: Admin approves all 4 users & assigns fleet vehicles to Rohan
    for uid in [h_reg["id"], w_reg["id"], d_reg["id"], other_d_reg["id"]]:
        assert client.patch(f"/api/admin/users/{uid}/approve", headers=admin_hdrs).status_code == 200
    for vid in veh_ids:
        upd_v = client.put(
            f"/api/admin/vehicles/{vid}",
            headers=admin_hdrs,
            json={"assigned_driver_user_id": d_reg["id"]},
        )
        assert upd_v.status_code == 200

    hosp_hdrs = _login_headers(client, "sassoon@hosp.org", "HospStrong!2026")
    wh_hdrs = _login_headers(client, "pimpri@wh.org", "WhStrong!2026")
    drv_hdrs = _login_headers(client, "rohan@delivery.org", "DelivStrong!2026")
    other_drv_hdrs = _login_headers(client, "other@delivery.org", "DelivStrong!2026")

    # Step 3: Hospital creates multi-product critical order -> pending_approval
    before_summary = client.get("/api/analytics/summary", headers=admin_hdrs).json()
    order_res = client.post(
        "/api/hospital/orders",
        headers=hosp_hdrs,
        json={
            "priority_level": "critical",
            "emergency_reason": "Mass casualty trauma intake",
            "items": [
                {"product_id": p1_id, "quantity_requested": 30},
                {"product_id": p2_id, "quantity_requested": 20},
            ],
        },
    )
    assert order_res.status_code == 201
    created_orders = order_res.json()["orders"]
    assert len(created_orders) == 2

    # Unapproved order MUST NOT increase actionable demand in optimization/analytics
    mid_summary = client.get("/api/analytics/summary", headers=admin_hdrs).json()
    assert mid_summary["total_actionable_demand_units"] == before_summary["total_actionable_demand_units"]
    assert mid_summary["pending_approval_demand_units"] >= 50

    # Step 4: Admin approves both order lines
    for ord_item in created_orders:
        ap_res = client.post(
            f"/api/admin/orders/{ord_item['id']}/approve",
            headers=admin_hdrs,
        )
        assert ap_res.status_code == 200
        assert ap_res.json()["status"] == "open"
        assert ap_res.json()["approval_status"] == "approved"

    after_approve_summary = client.get("/api/analytics/summary", headers=admin_hdrs).json()
    assert after_approve_summary["total_actionable_demand_units"] == before_summary["total_actionable_demand_units"] + 50

    # Step 5: Admin executes Lexicographic Priority Optimization
    opt_res = client.post("/api/optimization/priority", headers=admin_hdrs, json={})
    assert opt_res.status_code == 200
    run_id = opt_res.json()["id"]

    # Step 6: Admin generates OR-Tools OSM Dispatch Plan
    plan_res = client.post(
        "/api/routes/dispatch-plans",
        headers=admin_hdrs,
        json={"optimization_run_id": run_id, "routing_objective": "min_distance"},
    )
    assert plan_res.status_code == 201, plan_res.text
    plan = plan_res.json()
    assert plan["routing_source"] == "osm"
    assert len(plan["vehicle_assignments"]) >= 1

    # Step 7: Warehouse updates preparation status on its outgoing shipment
    wh_ships = client.get("/api/warehouse/shipments", headers=wh_hdrs).json()
    assert len(wh_ships) >= 1
    va_id = wh_ships[0]["assignment_id"]
    prep_res = client.patch(
        f"/api/warehouse/shipments/{va_id}/preparation",
        headers=wh_hdrs,
        json={"preparation_status": "ready_for_dispatch", "preparation_notes": "Sealed cold boxes"},
    )
    assert prep_res.status_code == 200
    assert prep_res.json()["preparation_status"] == "ready_for_dispatch"

    # Step 8: Delivery driver accesses assigned route, another driver gets 403
    drv_assignments = client.get("/api/delivery/assignments", headers=drv_hdrs).json()
    assert len(drv_assignments) >= 1
    target_assign = next(
        (a for a in drv_assignments if any(s["hospital_id"] == hosp1_id for s in a["stops"])),
        drv_assignments[0],
    )
    target_stop = next(
        (s for s in target_assign["stops"] if s["hospital_id"] == hosp1_id),
        target_assign["stops"][0],
    )
    stop_id = target_stop["id"]
    first_line = target_stop["shipment_lines"][0]

    # Other driver cannot view assignment or confirm stop
    assert client.get(f"/api/delivery/assignments/{target_assign['id']}", headers=other_drv_hdrs).status_code == 403
    assert client.post(
        f"/api/delivery/stops/{stop_id}/confirmation",
        headers=other_drv_hdrs,
        json={"items": [{"shipment_line_id": first_line["id"], "quantity_delivered": 1}]},
    ).status_code == 403

    # Transition stop: planned -> dispatched -> in_transit
    assert client.patch(
        f"/api/delivery/stops/{stop_id}/status",
        headers=drv_hdrs,
        json={"status": "dispatched", "notes": "Left warehouse gate"},
    ).status_code == 200
    assert client.patch(
        f"/api/delivery/stops/{stop_id}/status",
        headers=drv_hdrs,
        json={"status": "in_transit", "notes": "En route via Pune arterial"},
    ).status_code == 200

    # Over-delivery beyond quantity_planned is blocked (422)
    over_res = client.post(
        f"/api/delivery/stops/{stop_id}/confirmation",
        headers=drv_hdrs,
        json={
            "remarks": "Invalid excess",
            "items": [
                {
                    "shipment_line_id": first_line["id"],
                    "quantity_delivered": first_line["quantity_planned"] + 50,
                }
            ],
        },
    )
    assert over_res.status_code == 422

    # Partial delivery confirmation
    partial_qty = max(1.0, round(first_line["quantity_planned"] / 2.0, 2))
    partial_res = client.post(
        f"/api/delivery/stops/{stop_id}/confirmation",
        headers=drv_hdrs,
        json={
            "remarks": "Partial drop at ER bay",
            "items": [{"shipment_line_id": first_line["id"], "quantity_delivered": partial_qty}],
        },
    )
    assert partial_res.status_code == 200
    partial_stop = next(s for s in partial_res.json()["stops"] if s["id"] == stop_id)
    assert partial_stop["status"] == "partially_delivered"

    # Full delivery confirmation across all lines at this stop
    full_items = [
        {"shipment_line_id": ln["id"], "quantity_delivered": ln["quantity_planned"]}
        for ln in target_stop["shipment_lines"]
    ]
    full_res = client.post(
        f"/api/delivery/stops/{stop_id}/confirmation",
        headers=drv_hdrs,
        json={"remarks": "Signed by hospital pharmacy", "items": full_items},
    )
    assert full_res.status_code == 200
    full_stop = next(s for s in full_res.json()["stops"] if s["id"] == stop_id)
    assert full_stop["status"] == "delivered"

    # Duplicate confirmation on already-delivered stop blocked (409)
    dup_conf = client.post(
        f"/api/delivery/stops/{stop_id}/confirmation",
        headers=drv_hdrs,
        json={"remarks": "Duplicate click", "items": full_items},
    )
    assert dup_conf.status_code == 409

    # Step 9: Hospital tracks updated order timeline & notifications
    hosp_orders = client.get("/api/hospital/orders", headers=hosp_hdrs).json()
    tracked = next(o for o in hosp_orders if o["id"] == created_orders[0]["id"])
    assert tracked["approval_status"] == "approved"
    assert len(tracked["timeline"]) == 6

    hosp_notifs = client.get("/api/notifications", headers=hosp_hdrs).json()
    assert len(hosp_notifs) >= 1

    # Step 10: Admin verifies Analytics & Audit Logs
    overview = client.get("/api/analytics/overview", headers=admin_hdrs).json()
    assert overview["dispatch"]["total_delivered_quantity"] > 0

    audit_logs = client.get("/api/admin/audit-logs", headers=admin_hdrs).json()
    actions = {lg["action"] for lg in audit_logs}
    assert "admin.user_approved" in actions
    assert "admin.order_approved" in actions
    assert "optimization.executed" in actions
    assert "dispatch.plan_generated" in actions
    assert any("delivery" in a for a in actions)


# =============================================================================
# 5. NEW HOSPITAL / WAREHOUSE / DRIVER-VEHICLE ONBOARDING & SYSTEM-WIDE SYNC
# =============================================================================


def test_new_facility_and_driver_onboarding_syncs_across_system() -> None:
    """
    Verify registering a brand-new Hospital, brand-new Warehouse, and new Delivery Driver + Vehicle:
    - Starts inactive/unavailable while pending Admin approval (excluded from active org list & LP)
    - Automatically activates upon Admin approval, auto-generates Road corridors across all pairs,
      and becomes live in /api/hospitals, /api/warehouses, /api/admin/vehicles, and Optimization!
    """
    client, _ = _create_isolated_env()
    admin_hdrs = _login_headers(client, "admin@medilogix.org", "AdminStrong!2026")

    orgs_before = client.get("/api/auth/public-organizations").json()
    wh1_id = orgs_before["warehouses"][0]["id"]
    roads_before = len(client.get("/api/routes", headers=admin_hdrs).json())

    # 1. Brand-new Hospital registration
    hosp_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Dr. Sneha Patil",
            "email": "sneha@deenanath.org",
            "password": "HospNew!2026",
            "confirm_password": "HospNew!2026",
            "phone_number": "+91-9822112233",
            "role": "hospital",
            "new_hospital": {
                "name": "Deenanath Emergency Trauma Center",
                "area": "Erandwane",
                "city": "Pune",
                "latitude": 18.5089,
                "longitude": 73.8295,
                "bed_capacity": 320,
                "priority_level": "critical",
            },
        },
    )
    assert hosp_reg.status_code == 201, hosp_reg.text
    hosp_user = hosp_reg.json()["user"]
    new_hosp_code = hosp_user["associated_hospital_code"]
    assert new_hosp_code == "HOSP-09"

    # Before approval, HOSP-09 is inactive and NOT in public active list
    orgs_pending = client.get("/api/auth/public-organizations").json()
    assert all(h["code"] != "HOSP-09" for h in orgs_pending["hospitals"])

    # Admin approves -> HOSP-09 becomes active & road corridors auto-generated
    assert client.patch(f"/api/admin/users/{hosp_user['id']}/approve", headers=admin_hdrs).status_code == 200
    hosps_after = client.get("/api/hospitals", headers=admin_hdrs).json()
    h9 = next(h for h in hosps_after if h["code"] == "HOSP-09")
    assert h9["status"] == "active"
    assert h9["bed_capacity"] == 320
    assert h9["priority_level"] == "critical"

    roads_after_hosp = len(client.get("/api/routes", headers=admin_hdrs).json())
    assert roads_after_hosp == roads_before + 3  # 3 existing warehouses -> HOSP-09

    # 2. Brand-new Warehouse registration
    wh_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Vikram Joshi",
            "email": "vikram@vimanhub.org",
            "password": "WhNew!2026",
            "confirm_password": "WhNew!2026",
            "role": "warehouse",
            "new_warehouse": {
                "name": "Viman Nagar Cold-Chain Hub",
                "area": "Viman Nagar",
                "city": "Pune",
                "latitude": 18.5679,
                "longitude": 73.9143,
                "storage_capacity_units": 4000,
            },
        },
    )
    assert wh_reg.status_code == 201, wh_reg.text
    wh_user = wh_reg.json()["user"]
    assert wh_user["associated_warehouse_code"] == "WH-04"

    assert client.patch(f"/api/admin/users/{wh_user['id']}/approve", headers=admin_hdrs).status_code == 200
    whs_after = client.get("/api/warehouses", headers=admin_hdrs).json()
    w4 = next(w for w in whs_after if w["code"] == "WH-04")
    assert w4["status"] == "active"
    assert w4["storage_capacity_units"] == 4000

    roads_after_wh = len(client.get("/api/routes", headers=admin_hdrs).json())
    assert roads_after_wh == roads_after_hosp + 9  # WH-04 -> all 9 hospitals

    # 3. New Delivery Driver + Vehicle registration
    drv_reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Amol Shinde",
            "email": "amol@fleet.org",
            "password": "DrvNew!2026",
            "confirm_password": "DrvNew!2026",
            "phone_number": "+91-9890011223",
            "role": "delivery",
            "new_vehicle": {
                "warehouse_id": wh1_id,
                "vehicle_type": "cold_chain_truck",
                "capacity_kg": 1800,
                "vehicle_code": "MH12-MED-99",
            },
        },
    )
    assert drv_reg.status_code == 201, drv_reg.text
    drv_user = drv_reg.json()["user"]
    assert "MH12-MED-99" in drv_user["assigned_vehicle_codes"]

    # Before approval, vehicle is unavailable
    vehs_pending = client.get("/api/admin/vehicles", headers=admin_hdrs).json()
    v99_before = next(v for v in vehs_pending if v["vehicle_code"] == "MH12-MED-99")
    assert v99_before["status"] == "unavailable"

    # After approval, vehicle becomes available and linked to Amol
    assert client.patch(f"/api/admin/users/{drv_user['id']}/approve", headers=admin_hdrs).status_code == 200
    vehs_after = client.get("/api/admin/vehicles", headers=admin_hdrs).json()
    v99_after = next(v for v in vehs_after if v["vehicle_code"] == "MH12-MED-99")
    assert v99_after["status"] == "available"
    assert v99_after["assigned_driver_user_id"] == drv_user["id"]
    assert v99_after["capacity_kg"] == 1800

    # Verify LP optimization runs cleanly including the newly onboarded active hospital & corridors
    opt_res = client.post("/api/optimization/priority", headers=admin_hdrs, json={})
    assert opt_res.status_code == 200
    assert opt_res.json()["solver_status"] == "Optimal"
