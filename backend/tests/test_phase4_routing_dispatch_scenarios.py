"""
Comprehensive Phase 4 Backend Tests:
- Phase 4A: Google OR-Tools Multi-Depot Capacitated Vehicle Routing
- Phase 4B: Persistent Dispatch Plans, Vehicle Assignments, Stops, Shipment Lines & Lifecycle
- Phase 4C: Isolated Disaster & Disruption Scenario Simulation Engine
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
from app.optimization.vehicle_routing import (
    DepotRoutingInput,
    ShipmentLineInput,
    VRPStopInput,
    VRPVehicleInput,
    solve_depot_vrp,
    solve_multi_depot_vrp,
)
from app.utils.dataset_loader import seed_database_from_csv

SYNTHETIC_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def _create_seeded_client() -> TestClient:
    """Create isolated in-memory SQLite DB seeded with synthetic CSVs + FK enforcement."""
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


# =============================================================================
# PHASE 4A — OR-TOOLS VEHICLE ROUTING UNIT TESTS
# =============================================================================


def test_vrp_multi_stop_tour_and_capacity_enforcement() -> None:
    """Single vehicle combines multiple nearby hospitals when combined weight fits capacity."""
    depot = DepotRoutingInput(
        warehouse_id=1,
        warehouse_code="WH-01",
        warehouse_name="Pimpri Hub",
        area="Pimpri",
        latitude=18.6298,
        longitude=73.7997,
        vehicles=[
            VRPVehicleInput(1, "VEH-01", "medical_truck", 3000.0, "available"),
            VRPVehicleInput(2, "VEH-02", "medical_van", 1500.0, "maintenance"),  # unavailable
        ],
        stops=[
            VRPStopInput(
                hospital_id=1,
                hospital_code="HOSP-01",
                hospital_name="Hospital A",
                area="Aundh",
                priority_level="critical",
                latitude=18.5590,
                longitude=73.8077,
                corridor_distance_km=9.5,
                corridor_time_min=20.0,
                corridor_available=True,
                route_code="RT-001",
                shipment_lines=[
                    ShipmentLineInput(1, "PROD-01", "Oxygen", "cylinder", 50.0, 18.5)
                ],  # 925 kg
            ),
            VRPStopInput(
                hospital_id=2,
                hospital_code="HOSP-02",
                hospital_name="Hospital B",
                area="Baner",
                priority_level="high",
                latitude=18.5590,
                longitude=73.7868,
                corridor_distance_km=10.2,
                corridor_time_min=22.0,
                corridor_available=True,
                route_code="RT-002",
                shipment_lines=[
                    ShipmentLineInput(2, "PROD-02", "IV Fluids", "carton", 100.0, 12.0)
                ],  # 1200 kg
            ),
        ],
        allow_multi_trip=False,
        allow_split_deliveries=False,
    )

    result = solve_depot_vrp(depot)
    assert result.status == "Optimal"
    assert len(result.routes) == 1
    route = result.routes[0]
    # Unavailable vehicle VEH-02 must NOT be assigned
    assert route.vehicle_code == "VEH-01"
    # Both hospitals visited in a single multi-stop tour (925 + 1200 = 2125 kg <= 3000 kg)
    assert len(route.stops) == 2
    assert route.total_load_kg <= route.capacity_kg
    assert abs(route.total_load_kg - 2125.0) < 0.1
    assert route.route_coordinates[0]["node_type"] == "warehouse"
    assert route.route_coordinates[-1]["node_type"] == "warehouse_return"


def test_vrp_separate_depots_never_mix_origins() -> None:
    """Multi-depot solver keeps each warehouse's vehicles bound to its own depot."""
    depot_a = DepotRoutingInput(
        warehouse_id=1,
        warehouse_code="WH-01",
        warehouse_name="Pimpri Hub",
        area="Pimpri",
        latitude=18.6298,
        longitude=73.7997,
        vehicles=[VRPVehicleInput(1, "VEH-WH1-01", "truck", 2500.0, "available")],
        stops=[
            VRPStopInput(
                hospital_id=1,
                hospital_code="HOSP-01",
                hospital_name="H1",
                area="Aundh",
                priority_level="critical",
                latitude=18.5590,
                longitude=73.8077,
                corridor_distance_km=9.0,
                corridor_time_min=19.0,
                corridor_available=True,
                route_code="RT-01",
                shipment_lines=[ShipmentLineInput(1, "PROD-01", "O2", "cyl", 40.0, 18.5)],
            )
        ],
    )
    depot_b = DepotRoutingInput(
        warehouse_id=2,
        warehouse_code="WH-02",
        warehouse_name="Swargate Depot",
        area="Swargate",
        latitude=18.5018,
        longitude=73.8636,
        vehicles=[VRPVehicleInput(2, "VEH-WH2-01", "truck", 2500.0, "available")],
        stops=[
            VRPStopInput(
                hospital_id=2,
                hospital_code="HOSP-05",
                hospital_name="H5",
                area="Kondhwa",
                priority_level="critical",
                latitude=18.4695,
                longitude=73.8890,
                corridor_distance_km=5.5,
                corridor_time_min=12.0,
                corridor_available=True,
                route_code="RT-05",
                shipment_lines=[ShipmentLineInput(1, "PROD-01", "O2", "cyl", 50.0, 18.5)],
            )
        ],
    )

    res = solve_multi_depot_vrp([depot_a, depot_b])
    assert res.status == "Optimal"
    assert len(res.routes) == 2
    wh_to_veh = {r.warehouse_code: r.vehicle_code for r in res.routes}
    assert wh_to_veh["WH-01"] == "VEH-WH1-01"
    assert wh_to_veh["WH-02"] == "VEH-WH2-01"


def test_vrp_infeasible_on_insufficient_capacity_or_closed_road() -> None:
    """Verify clear infeasibility responses on capacity overflow and closed road corridors."""
    # Case 1: Insufficient single-trip capacity
    overload_depot = DepotRoutingInput(
        warehouse_id=1,
        warehouse_code="WH-01",
        warehouse_name="Pimpri Hub",
        area="Pimpri",
        latitude=18.6298,
        longitude=73.7997,
        vehicles=[VRPVehicleInput(1, "VEH-SMALL", "van", 500.0, "available")],
        stops=[
            VRPStopInput(
                hospital_id=1,
                hospital_code="HOSP-01",
                hospital_name="H1",
                area="Shivajinagar",
                priority_level="critical",
                latitude=18.5308,
                longitude=73.8475,
                corridor_distance_km=12.0,
                corridor_time_min=26.0,
                corridor_available=True,
                route_code="RT-001",
                shipment_lines=[ShipmentLineInput(1, "PROD-01", "O2", "cyl", 100.0, 18.5)],  # 1850 kg
            )
        ],
        allow_multi_trip=False,
        allow_split_deliveries=False,
    )
    cap_res = solve_depot_vrp(overload_depot)
    assert cap_res.status == "Infeasible"
    assert len(cap_res.infeasibility_reasons) >= 1
    assert "exceeds" in cap_res.infeasibility_reasons[0].lower()

    # Case 2: Closed road corridor cannot be used
    closed_depot = DepotRoutingInput(
        warehouse_id=1,
        warehouse_code="WH-01",
        warehouse_name="Pimpri Hub",
        area="Pimpri",
        latitude=18.6298,
        longitude=73.7997,
        vehicles=[VRPVehicleInput(1, "VEH-BIG", "truck", 5000.0, "available")],
        stops=[
            VRPStopInput(
                hospital_id=1,
                hospital_code="HOSP-01",
                hospital_name="H1",
                area="Shivajinagar",
                priority_level="critical",
                latitude=18.5308,
                longitude=73.8475,
                corridor_distance_km=12.0,
                corridor_time_min=26.0,
                corridor_available=False,
                route_code="RT-CLOSED-01",
                shipment_lines=[ShipmentLineInput(1, "PROD-01", "O2", "cyl", 20.0, 18.5)],
            )
        ],
    )
    closed_res = solve_depot_vrp(closed_depot)
    assert closed_res.status == "Infeasible"
    assert any("RT-CLOSED-01" in r for r in closed_res.infeasibility_reasons)


# =============================================================================
# PHASE 4B — DISPATCH PERSISTENCE & LIFECYCLE API TESTS
# =============================================================================


def test_dispatch_plan_persistence_conservation_and_lifecycle() -> None:
    """
    Verify:
    - Dispatch plan, vehicle assignments, ordered delivery stops, and shipment lines persist.
    - Total shipment quantities across all stops match source LP allocations identically.
    - Initial status is 'planned' with 0 delivered (never auto-delivered).
    - Invalid transitions are rejected (422); valid transitions work at plan and stop levels.
    - Live inventory & demand tables are untouched.
    """
    client = _create_seeded_client()
    inv_before = client.get("/api/inventory").json()
    dem_before = client.get("/api/demands").json()

    # Run Phase 3 Lexicographic Priority optimization
    opt_res = client.post("/api/optimization/priority", json={})
    assert opt_res.status_code == 200
    opt_data = opt_res.json()
    run_id = opt_data["id"]

    # Generate Dispatch Plan from completed optimization run
    dsp_res = client.post(
        "/api/routes/dispatch-plans",
        json={
            "optimization_run_id": run_id,
            "allow_multi_trip": True,
            "max_trips_per_vehicle": 3,
            "allow_split_deliveries": True,
        },
    )
    assert dsp_res.status_code == 201
    plan = dsp_res.json()

    # Initial lifecycle checks
    assert plan["status"] == "planned"
    assert plan["solver_status"] == "Optimal"
    assert plan["total_routes"] > 0
    assert plan["total_stops"] > 0
    assert plan["total_distance_km"] > 0

    # Verify stop ordering, capacity invariant, zero auto-delivery, and exact LP conservation
    planned_by_triplet: dict[tuple[str, str, str], float] = defaultdict(float)
    for va in plan["vehicle_assignments"]:
        assert va["status"] == "planned"
        assert va["total_load_kg"] <= va["capacity_kg"] + 0.1
        seqs = [s["stop_sequence"] for s in va["delivery_stops"]]
        assert seqs == list(range(1, len(seqs) + 1))
        for stop in va["delivery_stops"]:
            assert stop["status"] == "planned"
            for line in stop["shipment_lines"]:
                assert line["quantity_delivered"] == 0.0
                planned_by_triplet[
                    (va["warehouse_code"], stop["hospital_code"], line["product_code"])
                ] += float(line["quantity_planned"])

    lp_by_triplet: dict[tuple[str, str, str], float] = defaultdict(float)
    for alloc in opt_data["allocations"]:
        lp_by_triplet[
            (alloc["warehouse_code"], alloc["hospital_code"], alloc["product_code"])
        ] += float(alloc["quantity_allocated"])

    assert set(planned_by_triplet.keys()) == set(lp_by_triplet.keys())
    for key, lp_qty in lp_by_triplet.items():
        assert abs(planned_by_triplet[key] - lp_qty) <= 0.05

    # Invalid transition: cannot jump directly from planned -> delivered
    bad_trans = client.patch(
        f"/api/routes/dispatch-plans/{plan['id']}/status",
        json={"status": "delivered"},
    )
    assert bad_trans.status_code == 422

    # Valid transition: planned -> dispatched -> individual stop delivered -> partially_delivered
    disp_ok = client.patch(
        f"/api/routes/dispatch-plans/{plan['id']}/status",
        json={"status": "dispatched"},
    )
    assert disp_ok.status_code == 200
    assert disp_ok.json()["status"] == "dispatched"

    first_stop_id = plan["vehicle_assignments"][0]["delivery_stops"][0]["id"]
    stop_ok = client.patch(
        f"/api/routes/stops/{first_stop_id}/status",
        json={"status": "delivered", "notes": "Received by hospital pharmacy"},
    )
    assert stop_ok.status_code == 200
    updated_plan = stop_ok.json()
    assert updated_plan["status"] in {"partially_delivered", "delivered"}
    first_stop_after = updated_plan["vehicle_assignments"][0]["delivery_stops"][0]
    assert first_stop_after["status"] == "delivered"
    assert all(
        abs(line["quantity_delivered"] - line["quantity_planned"]) < 1e-4
        for line in first_stop_after["shipment_lines"]
    )

    # Verify history listing and missing run error
    plans_list = client.get("/api/routes/dispatch-plans").json()
    assert len(plans_list) == 1
    assert client.post("/api/routes/dispatch-plans", json={"optimization_run_id": 99999}).status_code == 404

    # Verify live inventory & demands were never modified
    assert client.get("/api/inventory").json() == inv_before
    assert client.get("/api/demands").json() == dem_before


# =============================================================================
# PHASE 4C — DISASTER & DISRUPTION SCENARIO SIMULATION TESTS
# =============================================================================


def test_disaster_scenarios_all_types_and_zero_live_mutation() -> None:
    """
    Verify:
    - Warehouse outage reduces supply & increases unmet demand.
    - Road closure affects routing/allocation.
    - Demand spike increases selected hospital demand.
    - Vehicle unavailability reduces available fleet count.
    - Combined disruption persists ScenarioRun cleanly.
    - Zero mutation of live inventory, demand, vehicles, roads, or baseline optimization run.
    """
    client = _create_seeded_client()

    # Capture live snapshots before simulations
    inv_before = client.get("/api/inventory").json()
    dem_before = client.get("/api/demands").json()
    veh_before = client.get("/api/routes/vehicles").json()
    roads_before = client.get("/api/routes").json()

    # Create baseline optimization run
    base_res = client.post("/api/optimization/priority", json={})
    assert base_res.status_code == 200
    base_run = base_res.json()
    base_id = base_run["id"]

    # 1. Warehouse outage
    wh_out = client.post(
        "/api/scenarios/simulate",
        json={
            "baseline_run_id": base_id,
            "name": "Swargate Depot Outage",
            "scenario_type": "warehouse_outage",
            "disabled_warehouse_codes": ["WH-02"],
        },
    )
    assert wh_out.status_code == 201
    wh_data = wh_out.json()
    assert wh_data["disrupted_metrics"]["total_unmet_demand"] > wh_data["baseline_metrics"]["total_unmet_demand"]
    assert wh_data["disrupted_metrics"]["available_vehicles_count"] < wh_data["baseline_metrics"]["available_vehicles_count"]

    # 2. Road closure
    road_res = client.post(
        "/api/scenarios/simulate",
        json={
            "baseline_run_id": base_id,
            "name": "Shivajinagar Corridor Flood Closure",
            "scenario_type": "road_closure",
            "closed_route_codes": ["RT-001", "RT-009", "RT-017"],  # All 3 corridors to HOSP-01
        },
    )
    assert road_res.status_code == 201
    road_data = road_res.json()
    # Closing all 3 corridors to HOSP-01 must drop critical fulfillment (HOSP-01 becomes unreachable)
    assert (
        road_data["disrupted_metrics"]["critical_fulfillment_pct"]
        < road_data["baseline_metrics"]["critical_fulfillment_pct"]
    )
    assert len(road_data["closed_corridors"]) == 3

    # 3. Demand spike on selected hospitals
    spike_res = client.post(
        "/api/scenarios/simulate",
        json={
            "baseline_run_id": base_id,
            "name": "Critical Trauma Surge +50%",
            "scenario_type": "demand_spike",
            "demand_spike_hospital_codes": ["HOSP-01", "HOSP-05"],
            "demand_spike_pct": 50.0,
        },
    )
    assert spike_res.status_code == 201
    spike_data = spike_res.json()
    assert spike_data["disrupted_metrics"]["total_demand"] > spike_data["baseline_metrics"]["total_demand"]

    # 4. Vehicle unavailability
    veh_res = client.post(
        "/api/scenarios/simulate",
        json={
            "baseline_run_id": base_id,
            "name": "Fleet Maintenance Outage",
            "scenario_type": "vehicle_unavailability",
            "disabled_vehicle_codes": ["VEH-WH-01-01", "VEH-WH-02-01"],
        },
    )
    assert veh_res.status_code == 201
    veh_data = veh_res.json()
    assert (
        veh_data["disrupted_metrics"]["available_vehicles_count"]
        == veh_data["baseline_metrics"]["available_vehicles_count"] - 2
    )

    # 5. Combined multi-factor disruption
    comb_res = client.post(
        "/api/scenarios/simulate",
        json={
            "baseline_run_id": base_id,
            "name": "Monsoon Emergency Combined Disruption",
            "scenario_type": "combined",
            "disabled_warehouse_codes": ["WH-03"],
            "closed_route_codes": ["RT-005"],
            "demand_spike_hospital_codes": ["HOSP-01"],
            "demand_spike_pct": 35.0,
            "disabled_vehicle_codes": ["VEH-WH-01-01"],
        },
    )
    assert comb_res.status_code == 201
    comb_data = comb_res.json()
    assert comb_data["comparison"]["demand_delta"] > 0
    assert comb_data["comparison"]["available_vehicles_delta"] < 0

    # Verify ScenarioRun history & detail retrieval
    sim_runs = client.get("/api/scenarios/runs").json()
    assert len(sim_runs) == 5
    detail = client.get(f"/api/scenarios/runs/{comb_data['id']}")
    assert detail.status_code == 200
    assert detail.json()["simulation_code"] == comb_data["simulation_code"]

    # Verify ZERO live mutation across all tables & baseline optimization run
    assert client.get("/api/inventory").json() == inv_before
    assert client.get("/api/demands").json() == dem_before
    assert client.get("/api/routes/vehicles").json() == veh_before
    assert client.get("/api/routes").json() == roads_before
    base_after = client.get(f"/api/optimization/runs/{base_id}").json()
    assert base_after["total_cost"] == base_run["total_cost"]
    assert base_after["total_allocated"] == base_run["total_allocated"]


# =============================================================================
# PHASE 4 AUDIT REGRESSION TESTS
# =============================================================================


def test_audit_regression_demand_kpi_clarity_and_subset_scenario_scope() -> None:
    """
    Regression test for Phase 4 Final Integration Audit findings:
    1. Analytics summary distinguishes open, partially_fulfilled, actionable, and run-scoped demand.
    2. Disaster simulation honors baseline run's selected_scope (no phantom demand from unselected hospitals).
    3. Multi-wave vehicle trip numbers normalize sequentially starting from 1 per vehicle.
    """
    client = _create_seeded_client()

    # Transition 1 demand to partially_fulfilled and 1 demand to fulfilled
    all_demands = client.get("/api/demands").json()
    part_dem = all_demands[0]
    fulf_dem = all_demands[1]
    assert client.put(f"/api/demands/{part_dem['id']}", json={"status": "partially_fulfilled"}).status_code == 200
    assert client.put(f"/api/demands/{fulf_dem['id']}", json={"status": "fulfilled"}).status_code == 200

    # Run optimization on a 6-hospital subset (excluding HOSP-04 and HOSP-06)
    subset_hospitals = ["HOSP-01", "HOSP-02", "HOSP-03", "HOSP-05", "HOSP-07", "HOSP-08"]
    opt_res = client.post(
        "/api/optimization/priority",
        json={"hospital_codes": subset_hospitals},
    )
    assert opt_res.status_code == 200
    opt_run = opt_res.json()

    # 1. Verify Dashboard analytics summary exposes consistent, unambiguous demand metrics
    summary = client.get("/api/analytics/summary").json()
    assert summary["total_partially_fulfilled_demand_units"] == part_dem["quantity_requested"]
    assert (
        summary["total_actionable_demand_units"]
        == summary["total_open_demand_units"] + summary["total_partially_fulfilled_demand_units"]
    )
    assert summary["latest_run_code"] == opt_run["run_code"]
    assert summary["latest_run_total_demand"] == opt_run["total_demand"]
    assert summary["latest_run_total_allocated"] == opt_run["total_allocated"]

    # Supply-demand gap total matches total_actionable_demand_units
    gap_rows = client.get("/api/analytics/supply-demand-gap").json()
    assert sum(r["total_open_demand"] for r in gap_rows) == summary["total_actionable_demand_units"]

    # 2. Verify Scenario Simulation against subset baseline preserves exact baseline demand scope
    sim_res = client.post(
        "/api/scenarios/simulate",
        json={
            "baseline_run_id": opt_run["id"],
            "name": "Vehicle Outage on Subset Baseline",
            "scenario_type": "vehicle_unavailability",
            "disabled_vehicle_codes": ["VEH-WH-01-01"],
        },
    )
    assert sim_res.status_code == 201
    sim_data = sim_res.json()
    assert sim_data["baseline_metrics"]["total_demand"] == opt_run["total_demand"]
    assert sim_data["disrupted_metrics"]["total_demand"] == opt_run["total_demand"]
    assert sim_data["comparison"]["demand_delta"] == 0.0

    # 3. Verify sequential trip numbering (1..K) per vehicle on generated dispatch plan
    dsp_res = client.post(
        "/api/routes/dispatch-plans",
        json={"optimization_run_id": opt_run["id"], "allow_multi_trip": True, "max_trips_per_vehicle": 3},
    )
    assert dsp_res.status_code == 201
    plan = dsp_res.json()
    trips_by_veh: dict[str, list[int]] = defaultdict(list)
    for va in plan["vehicle_assignments"]:
        trips_by_veh[va["vehicle_code"]].append(va["trip_number"])
    for veh_code, trip_nums in trips_by_veh.items():
        assert sorted(trip_nums) == list(range(1, len(trip_nums) + 1)), (
            f"Non-sequential wave numbers for {veh_code}: {trip_nums}"
        )
