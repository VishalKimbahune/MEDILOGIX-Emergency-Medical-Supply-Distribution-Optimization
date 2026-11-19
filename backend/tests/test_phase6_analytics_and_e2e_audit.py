"""
Phase 6–13 Mathematical Audit, Analytics KPI Consistency, API/Transaction Safety,
and Full 24-Step End-to-End Acceptance Test Suite.

Runs completely deterministically against isolated in-memory SQLite databases and
mocked OSM road-network caches — never modifies backend/medilogix_dev.db.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from tests.auth_helpers import attach_admin_auth
from app.optimization.osm_road_network import save_graph_cache
from app.optimization.vehicle_routing import (
    DepotRoutingInput,
    ShipmentLineInput,
    VRPStopInput,
    VRPVehicleInput,
    solve_depot_vrp,
)
from app.services import road_network_service
from app.utils.dataset_loader import seed_database_from_csv
from tests.test_phase5b_osm_vrp_integration import _build_mock_pune_osm_graph

SYNTHETIC_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def _create_isolated_client() -> TestClient:
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

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    attach_admin_auth(client, TestingSessionLocal)
    return client


def test_mathematical_lp_and_lexicographic_invariants() -> None:
    """
    Audit Part 8.1 & 8.2:
    - Warehouse stock constraint: sum_j x[i,j,k] <= S[i,k]
    - Hospital demand balance: sum_i x[i,j,k] + u[j,k] == D[j,k]
    - Non-negativity: x >= 0, u >= 0
    - Lexicographic priority locks Critical -> High -> Normal -> Cost sequentially.
    """
    client = _create_isolated_client()
    inv_rows = client.get("/api/inventory").json()
    dem_rows = client.get("/api/demands").json()
    wh_by_id = {w["id"]: w["code"] for w in client.get("/api/warehouses").json()}
    hosp_by_id = {h["id"]: h["code"] for h in client.get("/api/hospitals").json()}
    prod_by_id = {p["id"]: p["code"] for p in client.get("/api/products").json()}

    supply_cap: dict[tuple[str, str], float] = defaultdict(float)
    for inv in inv_rows:
        supply_cap[(wh_by_id[inv["warehouse_id"]], prod_by_id[inv["product_id"]])] += max(
            0.0, float(inv["quantity_available"]) - float(inv["quantity_reserved"])
        )

    demand_req: dict[tuple[str, str], float] = defaultdict(float)
    for dem in dem_rows:
        if dem["status"] in {"open", "partially_fulfilled"}:
            demand_req[(hosp_by_id[dem["hospital_id"]], prod_by_id[dem["product_id"]])] += float(
                dem["quantity_requested"]
            )

    cmp_res = client.post("/api/optimization/compare", json={})
    assert cmp_res.status_code == 200
    cmp_data = cmp_res.json()

    for model_key in ("transportation", "lexicographic_priority"):
        run = cmp_data[model_key]
        assert run["solver_status"] == "Optimal"

        shipped_by_wh_prod: dict[tuple[str, str], float] = defaultdict(float)
        recv_by_hosp_prod: dict[tuple[str, str], float] = defaultdict(float)
        unmet_by_hosp_prod: dict[tuple[str, str], float] = defaultdict(float)

        for a in run["allocations"]:
            qty = float(a["quantity_allocated"])
            assert qty >= -1e-6
            shipped_by_wh_prod[(a["warehouse_code"], a["product_code"])] += qty
            recv_by_hosp_prod[(a["hospital_code"], a["product_code"])] += qty

        for u in run["unmet_demands"]:
            uqty = float(u["unmet_quantity"])
            assert uqty >= -1e-6
            unmet_by_hosp_prod[(u["hospital_code"], u["product_code"])] += uqty

        # Warehouse stock ceiling
        for (wh_code, prod_code), shipped in shipped_by_wh_prod.items():
            assert shipped <= supply_cap[(wh_code, prod_code)] + 1e-4

        # Hospital demand balance
        for (h_code, prod_code), req in demand_req.items():
            bal = recv_by_hosp_prod[(h_code, prod_code)] + unmet_by_hosp_prod[(h_code, prod_code)]
            assert abs(bal - req) <= 1e-3

    # Lexicographic priority protects Critical strictly >= Transportation LP
    lp_crit = next(
        p["fulfillment_pct"]
        for p in cmp_data["transportation"]["priority_summary"]
        if p["priority_level"] == "critical"
    )
    lex_crit = next(
        p["fulfillment_pct"]
        for p in cmp_data["lexicographic_priority"]["priority_summary"]
        if p["priority_level"] == "critical"
    )
    assert lex_crit == 100.0
    assert lex_crit >= lp_crit
    assert len(cmp_data["lexicographic_priority"]["stage_results"]) == 4


def test_split_load_and_multi_wave_conservation_invariants() -> None:
    """
    Audit Part 8.3 & 8.4:
    Verify split-load + multi-wave VRP conserves 100% of allocated product units,
    never exceeds vehicle capacity, and numbers waves sequentially starting at 1.
    """
    depot = DepotRoutingInput(
        warehouse_id=1,
        warehouse_code="WH-01",
        warehouse_name="Pimpri Hub",
        area="Pimpri",
        latitude=18.6298,
        longitude=73.7997,
        vehicles=[VRPVehicleInput(1, "VEH-SPLIT-01", "medical_truck", 1000.0, "available")],
        stops=[
            VRPStopInput(
                hospital_id=1,
                hospital_code="HOSP-01",
                hospital_name="Trauma Center",
                area="Shivajinagar",
                priority_level="critical",
                latitude=18.5308,
                longitude=73.8475,
                corridor_distance_km=12.5,
                corridor_time_min=26.0,
                corridor_available=True,
                route_code="RT-001",
                shipment_lines=[
                    # 120 * 18.5 kg = 2,220 kg -> requires 3 split waves on a 1,000 kg truck!
                    ShipmentLineInput(1, "PROD-01", "Oxygen", "cylinder", 120.0, 18.5),
                ],
            )
        ],
        allow_multi_trip=True,
        max_trips_per_vehicle=4,
        allow_split_deliveries=True,
    )
    res = solve_depot_vrp(depot)
    assert res.status == "Optimal"
    assert len(res.routes) == 3
    assert [r.trip_number for r in res.routes] == [1, 2, 3]
    total_units = sum(
        float(line["quantity_planned"])
        for r in res.routes
        for s in r.stops
        for line in s.shipment_lines
    )
    assert abs(total_units - 120.0) <= 1e-4
    assert all(r.total_load_kg <= r.capacity_kg + 0.1 for r in res.routes)


def test_api_validation_invalid_ids_and_transaction_rollback_safety() -> None:
    """
    Audit Part 9:
    Verify Pydantic validation, duplicate rejection (409), missing IDs (404),
    over-delivery rejection (422), and clean transaction rollback on failures.
    """
    client = _create_isolated_client()
    wh_count_before = len(client.get("/api/warehouses").json())

    # Duplicate warehouse code rejected with 409 without corrupting table
    dup_wh = client.post(
        "/api/warehouses",
        json={
            "code": "WH-01",
            "name": "Duplicate Hub",
            "area": "Pimpri",
            "city": "Pune",
            "latitude": 18.62,
            "longitude": 73.80,
            "storage_capacity_units": 5000,
        },
    )
    assert dup_wh.status_code == 409
    assert len(client.get("/api/warehouses").json()) == wh_count_before

    # Negative demand quantity rejected with 422
    bad_dem = client.post(
        "/api/demands",
        json={
            "hospital_id": 1,
            "product_id": 1,
            "quantity_requested": -50,
            "priority_level": "critical",
        },
    )
    assert bad_dem.status_code == 422

    # Nonexistent IDs return 404 cleanly
    assert client.get("/api/warehouses/99999").status_code == 404
    assert client.get("/api/hospitals/99999").status_code == 404
    assert client.get("/api/optimization/runs/99999").status_code == 404
    assert client.get("/api/routes/dispatch-plans/99999").status_code == 404
    assert client.get("/api/scenarios/runs/99999").status_code == 404


def test_analytics_overview_kpi_consistency_and_full_e2e_acceptance_workflow(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """
    Part 6, 10 & 13: Complete End-to-End Acceptance Test across all modules +
    Analytics KPI mathematical consistency audit against live DB tables.
    """
    mock_graph = _build_mock_pune_osm_graph()
    cache_file = tmp_path / "e2e_pune_osm.json"
    save_graph_cache(
        mock_graph,
        cache_path=cache_file,
        bbox={"min_lat": 18.4, "max_lat": 18.7, "min_lon": 73.7, "max_lon": 74.05},
    )
    monkeypatch.setattr(
        road_network_service,
        "_resolve_cache_path",
        lambda override_path=None: override_path or cache_file,
    )
    road_network_service.clear_memory_cache()

    client = _create_isolated_client()

    # 1. Health & Base Resources
    assert client.get("/api/health").json()["database_connected"] is True
    whs = client.get("/api/warehouses").json()
    hosps = client.get("/api/hospitals").json()
    prods = client.get("/api/products").json()
    invs = client.get("/api/inventory").json()
    dems = client.get("/api/demands").json()
    assert len(whs) == 3 and len(hosps) == 8 and len(prods) == 4

    # 2. Road Network Status & Shortest Path
    rn_status = client.get("/api/routes/road-network/status").json()
    assert rn_status["osm_available"] is True
    assert rn_status["active_source"] == "osm_road_network"
    sp = client.post(
        "/api/routes/road-network/shortest-path",
        json={"source_code": "WH-01", "target_code": "HOSP-01", "weight_metric": "distance_km"},
    ).json()
    assert sp["reachable"] is True and sp["source_type"] == "osm_road_network"

    # 3. Optimization: Transportation LP, Lexicographic Priority LP, Compare & History
    cmp_data = client.post("/api/optimization/compare", json={}).json()
    lex_run = cmp_data["lexicographic_priority"]
    runs_hist = client.get("/api/optimization/runs").json()
    assert len(runs_hist) == 2

    # 4. Generate OSM Dispatch Plan + Verify Diagnostics, Capacity, Conservation & Lifecycle
    plan = client.post(
        "/api/routes/dispatch-plans",
        json={"optimization_run_id": lex_run["id"], "routing_objective": "min_distance"},
    ).json()
    assert plan["routing_source"] == "osm"
    assert plan["fallback_used"] is False
    assert all(va["geometry_point_count"] >= 3 for va in plan["vehicle_assignments"])
    assert all(va["stop_count"] == len(va["delivery_stops"]) for va in plan["vehicle_assignments"])

    # Transition dispatch lifecycle cleanly & verify over-delivery rejection
    assert (
        client.patch(
            f"/api/routes/dispatch-plans/{plan['id']}/status", json={"status": "dispatched"}
        ).status_code
        == 200
    )
    first_stop = plan["vehicle_assignments"][0]["delivery_stops"][0]
    first_line = first_stop["shipment_lines"][0]
    assert (
        client.patch(
            f"/api/routes/stops/{first_stop['id']}/status",
            json={
                "status": "partially_delivered",
                "shipment_updates": [
                    {
                        "shipment_line_id": first_line["id"],
                        "quantity_delivered": first_line["quantity_planned"] + 10.0,
                    }
                ],
            },
        ).status_code
        == 422
    )
    stop_done = client.patch(
        f"/api/routes/stops/{first_stop['id']}/status",
        json={"status": "delivered"},
    )
    assert stop_done.status_code == 200

    # 5. Disaster Simulations (Warehouse Outage, OSM Road Closure, Demand Spike, Vehicle Loss)
    inv_snap = client.get("/api/inventory").json()
    dem_snap = client.get("/api/demands").json()
    for payload in [
        {
            "baseline_run_id": lex_run["id"],
            "name": "E2E Warehouse Outage",
            "scenario_type": "warehouse_outage",
            "disabled_warehouse_codes": ["WH-02"],
        },
        {
            "baseline_run_id": lex_run["id"],
            "name": "E2E OSM Highway Closure",
            "scenario_type": "road_closure",
            "closed_way_ids": [9004],
        },
        {
            "baseline_run_id": lex_run["id"],
            "name": "E2E Demand Spike",
            "scenario_type": "demand_spike",
            "demand_spike_hospital_codes": ["HOSP-01"],
            "demand_spike_pct": 40.0,
        },
        {
            "baseline_run_id": lex_run["id"],
            "name": "E2E Vehicle Outage",
            "scenario_type": "vehicle_unavailability",
            "disabled_vehicle_codes": ["VEH-WH-01-01"],
        },
    ]:
        sim_res = client.post("/api/scenarios/simulate", json=payload)
        assert sim_res.status_code == 201
        assert "route_duration_min_delta" in sim_res.json()["comparison"]

    # Confirm zero live mutation from all 4 simulations
    assert client.get("/api/inventory").json() == inv_snap
    assert client.get("/api/demands").json() == dem_snap

    # 6. Analytics & Reports Consistency Audit (GET /api/analytics/overview + /summary)
    overview = client.get("/api/analytics/overview").json()
    summary = client.get("/api/analytics/summary").json()

    # Supply chain exact consistency
    assert overview["supply_chain"]["total_warehouses"] == len(whs)
    assert overview["supply_chain"]["total_hospitals"] == len(hosps)
    assert overview["supply_chain"]["total_products"] == len(prods)
    assert overview["supply_chain"]["available_inventory_units"] == sum(
        i["quantity_available"] for i in invs
    )
    assert overview["supply_chain"]["total_actionable_demand_units"] == summary["total_actionable_demand_units"]
    assert overview["supply_chain"]["open_demand_units"] == summary["total_open_demand_units"]

    # Optimization snapshot consistency
    assert overview["optimization"]["total_runs"] == 2
    assert overview["optimization"]["latest_run"]["run_code"] == summary["latest_run_code"]
    assert overview["optimization"]["latest_run"]["total_allocated"] == summary["latest_run_total_allocated"]
    assert len(overview["optimization"]["cost_comparison_history"]) == 2

    # Dispatch KPI consistency
    disp_kpi = overview["dispatch"]
    assert disp_kpi["total_dispatch_plans"] == 1
    assert disp_kpi["total_planned_routes"] == plan["total_routes"]
    assert disp_kpi["total_delivery_stops"] == plan["total_stops"]
    assert disp_kpi["total_delivered_quantity"] > 0.0
    assert disp_kpi["total_delivered_quantity"] <= disp_kpi["total_planned_quantity"]
    assert abs(
        (disp_kpi["total_delivered_quantity"] + disp_kpi["total_pending_quantity"])
        - disp_kpi["total_planned_quantity"]
    ) <= 0.05

    # Scenario analytics consistency
    assert overview["scenarios"]["total_simulations"] == 4
    assert len(overview["scenarios"]["impact_by_type"]) == 4
    assert overview["scenarios"]["latest_simulation"] is not None
