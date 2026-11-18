"""
Comprehensive Unit & API Integration Tests for MEDILOGIX Operations Research Engine.

Covers all 17 Phase 3 verification criteria:
- Basic, multi-warehouse, multi-hospital, and multi-commodity transportation LP
- Insufficient supply vs. excess supply scenarios
- Sequential 4-stage lexicographic priority (Critical > High > Normal > Cost)
- Zero-demand priority tier handling (division-by-zero prevention)
- Unavailable route enforcement (A_ij = False -> x_ijk = 0)
- Warehouse stock & hospital demand mathematical constraint verification
- Infeasible model and invalid input handling
- Immutable historical optimization run persistence & repeated runs
- Full API integration (/transportation, /priority, /compare, /runs, /runs/{id}, /analytics/summary)
- Data integrity (original inventory & demands remain untouched after solving)
- NetworkX shortest path and disaster scenario engine
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.connection import get_db
from app.main import app
from app.optimization.linear_programming import (
    NetworkOptimizationInput,
    OptimizationValidationError,
)
from app.optimization.priority import solve_lexicographic_priority_optimization
from app.optimization.shortest_path import build_logistics_graph, compute_shortest_path
from app.optimization.transportation import solve_transportation_problem
from app.simulation.scenario_engine import DisasterScenarioConfig, apply_disaster_scenario
from app.utils.dataset_loader import seed_database_from_csv

SYNTHETIC_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "synthetic"


def _sample_shortage_network() -> NetworkOptimizationInput:
    """
    Controlled-shortage network:
    - Total supply = 100 units across 2 warehouses (WH-01: 60, WH-02: 40)
    - Total demand = 150 units (Critical: 60, High: 50, Normal: 40)
    - Normal hospital is deliberately cheaper to ship to than Critical/High,
      testing priority protection vs. pure cost minimization.
    """
    return NetworkOptimizationInput(
        warehouses=["WH-01", "WH-02"],
        hospitals=["HOSP-CRIT", "HOSP-HIGH", "HOSP-NORM"],
        products=["PROD-01"],
        hospital_priorities={
            "HOSP-CRIT": "critical",
            "HOSP-HIGH": "high",
            "HOSP-NORM": "normal",
        },
        supply={("WH-01", "PROD-01"): 60.0, ("WH-02", "PROD-01"): 40.0},
        demand={
            ("HOSP-CRIT", "PROD-01"): 60.0,
            ("HOSP-HIGH", "PROD-01"): 50.0,
            ("HOSP-NORM", "PROD-01"): 40.0,
        },
        unit_cost={
            ("WH-01", "HOSP-CRIT", "PROD-01"): 50.0,
            ("WH-01", "HOSP-HIGH", "PROD-01"): 25.0,
            ("WH-01", "HOSP-NORM", "PROD-01"): 5.0,
            ("WH-02", "HOSP-CRIT", "PROD-01"): 45.0,
            ("WH-02", "HOSP-HIGH", "PROD-01"): 20.0,
            ("WH-02", "HOSP-NORM", "PROD-01"): 8.0,
        },
        route_availability={
            ("WH-01", "HOSP-CRIT"): True,
            ("WH-01", "HOSP-HIGH"): True,
            ("WH-01", "HOSP-NORM"): True,
            ("WH-02", "HOSP-CRIT"): True,
            ("WH-02", "HOSP-HIGH"): True,
            ("WH-02", "HOSP-NORM"): True,
        },
    )


def _assert_mathematical_constraints(
    net: NetworkOptimizationInput,
    outcome_allocations: list[dict[str, Any]],
    outcome_unmet: list[dict[str, Any]],
) -> None:
    """Verify every LP mathematical constraint holds on solved output."""
    wh_prod_shipped: dict[tuple[str, str], float] = defaultdict(float)
    hosp_prod_received: dict[tuple[str, str], float] = defaultdict(float)

    for alloc in outcome_allocations:
        qty = float(alloc["quantity_allocated"])
        wh = alloc["warehouse_code"]
        hosp = alloc["hospital_code"]
        prod = alloc["product_code"]
        # Non-negativity
        assert qty >= 0.0
        # Route availability
        assert net.route_availability.get((wh, hosp), True) is True
        wh_prod_shipped[(wh, prod)] += qty
        hosp_prod_received[(hosp, prod)] += qty

    # Constraint A: Warehouse stock limits sum_j x_ijk <= S_ik
    for (wh, prod), shipped in wh_prod_shipped.items():
        avail = float(net.supply.get((wh, prod), 0.0))
        assert shipped <= avail + 1e-4

    # Constraint B: Hospital demand balance sum_i x_ijk + u_jk == D_jk
    unmet_map = {
        (item["hospital_code"], item["product_code"]): float(item["unmet_quantity"])
        for item in outcome_unmet
    }
    for hosp in net.hospitals:
        for prod in net.products:
            req = float(net.demand.get((hosp, prod), 0.0))
            rec = hosp_prod_received[(hosp, prod)]
            unmet = unmet_map.get((hosp, prod), 0.0)
            assert unmet >= 0.0
            assert abs((rec + unmet) - req) <= 1e-3


def _create_seeded_test_client() -> TestClient:
    """Create a TestClient backed by an isolated in-memory SQLite DB seeded with synthetic CSVs."""
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
    return TestClient(app)


# 1, 2, 3, 5, 11, 12, 17: Basic & shortage transportation LP + exact cost + constraint verification
def test_transportation_lp_solves_optimally() -> None:
    net = _sample_shortage_network()
    outcome = solve_transportation_problem(net, allow_unmet_demand=True)

    assert outcome.solver_status == "Optimal"
    assert outcome.total_demand == 150.0
    assert outcome.total_allocated == 100.0
    assert outcome.total_unmet_demand == 50.0
    assert abs(outcome.fulfillment_percentage - 66.67) < 0.02
    # Pure cost minimization should fulfill cheapest Normal (40 * 5 = 200),
    # then High (40 * 20 from WH-02 + 10 * 25 from WH-01 = 1050), then 10 Crit from WH-01 (10 * 50 = 500) -> 1750
    assert abs(outcome.total_cost - 1750.0) < 1e-2
    assert len(outcome.stage_results) == 2
    _assert_mathematical_constraints(net, outcome.allocations, outcome.unmet_demands)


# 4, 6: Multi-product excess supply achieves 100% fulfillment & minimum cost
def test_multi_commodity_excess_supply() -> None:
    net = NetworkOptimizationInput(
        warehouses=["WH-01", "WH-02"],
        hospitals=["HOSP-01", "HOSP-02"],
        products=["PROD-01", "PROD-02"],
        hospital_priorities={"HOSP-01": "critical", "HOSP-02": "normal"},
        supply={
            ("WH-01", "PROD-01"): 200.0,
            ("WH-02", "PROD-01"): 200.0,
            ("WH-01", "PROD-02"): 300.0,
            ("WH-02", "PROD-02"): 300.0,
        },
        demand={
            ("HOSP-01", "PROD-01"): 80.0,
            ("HOSP-02", "PROD-01"): 70.0,
            ("HOSP-01", "PROD-02"): 100.0,
            ("HOSP-02", "PROD-02"): 120.0,
        },
        unit_cost={
            ("WH-01", "HOSP-01", "PROD-01"): 10.0,
            ("WH-02", "HOSP-01", "PROD-01"): 30.0,
            ("WH-01", "HOSP-02", "PROD-01"): 25.0,
            ("WH-02", "HOSP-02", "PROD-01"): 12.0,
            ("WH-01", "HOSP-01", "PROD-02"): 6.0,
            ("WH-02", "HOSP-01", "PROD-02"): 18.0,
            ("WH-01", "HOSP-02", "PROD-02"): 15.0,
            ("WH-02", "HOSP-02", "PROD-02"): 5.0,
        },
        route_availability={
            ("WH-01", "HOSP-01"): True,
            ("WH-01", "HOSP-02"): True,
            ("WH-02", "HOSP-01"): True,
            ("WH-02", "HOSP-02"): True,
        },
    )

    outcome = solve_transportation_problem(net, allow_unmet_demand=False)
    assert outcome.solver_status == "Optimal"
    assert outcome.total_demand == 370.0
    assert outcome.total_allocated == 370.0
    assert outcome.total_unmet_demand == 0.0
    assert outcome.fulfillment_percentage == 100.0
    # Expected optimal cost: 80*10 + 70*12 + 100*6 + 120*5 = 800 + 840 + 600 + 600 = 2840
    assert abs(outcome.total_cost - 2840.0) < 1e-2
    assert len(outcome.product_summary) == 2
    assert all(p["fulfillment_pct"] == 100.0 for p in outcome.product_summary)
    assert all(w["remaining_stock"] > 0 for w in outcome.warehouse_utilization)
    _assert_mathematical_constraints(net, outcome.allocations, outcome.unmet_demands)


# 7: Lexicographic priority protects Critical > High > Normal > Cost
def test_lexicographic_priority_protects_critical_hospitals_first() -> None:
    net = _sample_shortage_network()
    outcome = solve_lexicographic_priority_optimization(net)

    assert outcome.solver_status == "Optimal"
    assert outcome.tier_unmet_fractions["critical"] == 0.0
    assert abs(outcome.tier_unmet_fractions["high"] - 0.2) < 1e-5
    assert outcome.tier_unmet_fractions["normal"] == 1.0
    assert len(outcome.stage_results) == 4
    assert all(stage["solver_status"] == "Optimal" for stage in outcome.stage_results)
    # Priority cost > pure cost-only LP (1750) because Critical/High corridors cost more
    assert outcome.total_cost > 1750.0
    _assert_mathematical_constraints(net, outcome.allocations, outcome.unmet_demands)


# 8, 9: High priority beats Normal when Critical tier has zero demand (no division by zero)
def test_high_priority_over_normal_with_zero_critical_demand() -> None:
    net = NetworkOptimizationInput(
        warehouses=["WH-01"],
        hospitals=["HOSP-HIGH", "HOSP-NORM"],
        products=["PROD-01"],
        hospital_priorities={"HOSP-HIGH": "high", "HOSP-NORM": "normal"},
        supply={("WH-01", "PROD-01"): 50.0},
        demand={("HOSP-HIGH", "PROD-01"): 50.0, ("HOSP-NORM", "PROD-01"): 50.0},
        unit_cost={
            ("WH-01", "HOSP-HIGH", "PROD-01"): 40.0,
            ("WH-01", "HOSP-NORM", "PROD-01"): 5.0,
        },
        route_availability={("WH-01", "HOSP-HIGH"): True, ("WH-01", "HOSP-NORM"): True},
    )

    outcome = solve_lexicographic_priority_optimization(net)
    assert outcome.solver_status == "Optimal"
    # Stage 1 (Critical) skipped cleanly with 0.0 fraction
    assert outcome.stage_results[0]["skipped"] is True
    assert outcome.tier_unmet_fractions["critical"] == 0.0
    # High gets all 50 units (0% unmet), Normal gets 0 (100% unmet)
    assert outcome.tier_unmet_fractions["high"] == 0.0
    assert outcome.tier_unmet_fractions["normal"] == 1.0
    assert abs(outcome.total_cost - 2000.0) < 1e-2
    _assert_mathematical_constraints(net, outcome.allocations, outcome.unmet_demands)


# 10: Unavailable transportation routes carry strictly zero shipment
def test_unavailable_routes_are_strictly_blocked() -> None:
    net = NetworkOptimizationInput(
        warehouses=["WH-01", "WH-02"],
        hospitals=["HOSP-01"],
        products=["PROD-01"],
        hospital_priorities={"HOSP-01": "critical"},
        supply={("WH-01", "PROD-01"): 100.0, ("WH-02", "PROD-01"): 40.0},
        demand={("HOSP-01", "PROD-01"): 80.0},
        unit_cost={
            ("WH-01", "HOSP-01", "PROD-01"): 2.0,
            ("WH-02", "HOSP-01", "PROD-01"): 30.0,
        },
        route_availability={
            ("WH-01", "HOSP-01"): False,  # Cheaper direct corridor is CLOSED
            ("WH-02", "HOSP-01"): True,
        },
    )

    outcome = solve_lexicographic_priority_optimization(net)
    assert outcome.solver_status == "Optimal"
    assert outcome.total_allocated == 40.0
    assert outcome.total_unmet_demand == 40.0
    assert all(a["warehouse_code"] != "WH-01" for a in outcome.allocations)
    _assert_mathematical_constraints(net, outcome.allocations, outcome.unmet_demands)


# 13: Infeasible model & invalid input validation
def test_infeasible_strict_lp_and_invalid_inputs() -> None:
    shortage_net = _sample_shortage_network()
    infeasible_outcome = solve_transportation_problem(shortage_net, allow_unmet_demand=False)
    assert infeasible_outcome.solver_status == "Infeasible"
    assert infeasible_outcome.allocations == []

    # Invalid negative supply raises OptimizationValidationError
    bad_supply_net = NetworkOptimizationInput(
        warehouses=["WH-01"],
        hospitals=["HOSP-01"],
        products=["PROD-01"],
        hospital_priorities={"HOSP-01": "critical"},
        supply={("WH-01", "PROD-01"): -10.0},
        demand={("HOSP-01", "PROD-01"): 20.0},
        unit_cost={("WH-01", "HOSP-01", "PROD-01"): 10.0},
        route_availability={("WH-01", "HOSP-01"): True},
    )
    with pytest.raises(OptimizationValidationError):
        solve_transportation_problem(bad_supply_net)

    # Empty warehouses raises OptimizationValidationError
    empty_wh_net = NetworkOptimizationInput(
        warehouses=[],
        hospitals=["HOSP-01"],
        products=["PROD-01"],
        hospital_priorities={"HOSP-01": "critical"},
        supply={},
        demand={("HOSP-01", "PROD-01"): 20.0},
        unit_cost={},
    )
    with pytest.raises(OptimizationValidationError):
        solve_lexicographic_priority_optimization(empty_wh_net)


# 14, 15, 16, 17: Full API integration, persistence, immutability, compare, and data integrity
def test_api_optimization_persistence_comparison_and_data_integrity() -> None:
    client = _create_seeded_test_client()

    # Capture original inventory & demand snapshots to verify zero mutation
    inv_before = client.get("/api/inventory").json()
    dem_before = client.get("/api/demands").json()

    # Run 1: Multi-Commodity Transportation LP on full synthetic dataset
    res_transport = client.post("/api/optimization/transportation", json={})
    assert res_transport.status_code == 200
    t_data = res_transport.json()
    assert t_data["solver_status"] == "Optimal"
    assert t_data["total_demand"] > 0
    assert abs((t_data["total_allocated"] + t_data["total_unmet_demand"]) - t_data["total_demand"]) < 1e-2
    assert len(t_data["warehouse_utilization"]) == 3
    assert len(t_data["product_summary"]) == 4
    assert len(t_data["hospital_summary"]) == 8
    assert len(t_data["priority_summary"]) == 3
    assert "formulation_summary" in t_data

    # Run 2: Lexicographic Priority LP on same dataset
    res_priority = client.post("/api/optimization/priority", json={})
    assert res_priority.status_code == 200
    p_data = res_priority.json()
    assert p_data["solver_status"] == "Optimal"
    assert p_data["id"] != t_data["id"]
    assert p_data["run_code"] != t_data["run_code"]
    # Critical hospitals must be 100% fulfilled under lexicographic priority on synthetic data
    crit_summary = next(x for x in p_data["priority_summary"] if x["priority_level"] == "critical")
    assert crit_summary["fulfillment_pct"] == 100.0
    assert crit_summary["total_unmet"] == 0.0

    # Verify Run 1 historical record remained immutable
    run1_detail = client.get(f"/api/optimization/runs/{t_data['id']}")
    assert run1_detail.status_code == 200
    assert run1_detail.json()["run_code"] == t_data["run_code"]
    assert run1_detail.json()["total_cost"] == t_data["total_cost"]
    assert len(run1_detail.json()["allocations"]) == len(t_data["allocations"])

    # Verify runs list preserves both runs
    runs_list = client.get("/api/optimization/runs").json()
    assert len(runs_list) == 2

    # Verify Dashboard analytics summary displays latest run results
    summary = client.get("/api/analytics/summary").json()
    assert summary["latest_run_code"] == p_data["run_code"]
    assert summary["latest_distribution_cost"] == p_data["total_cost"]
    assert summary["latest_demand_fulfillment_pct"] is not None

    # Verify Model Comparison endpoint
    comp_res = client.post("/api/optimization/compare", json={})
    assert comp_res.status_code == 200
    comp = comp_res.json()
    assert comp["transportation"]["solver_status"] == "Optimal"
    assert comp["lexicographic_priority"]["solver_status"] == "Optimal"
    assert "tier_comparison" in comp["comparison_metrics"]
    assert comp["lexicographic_priority"]["total_cost"] >= comp["transportation"]["total_cost"] - 1e-2

    # Verify subset selection and invalid code rejection
    subset_res = client.post(
        "/api/optimization/priority",
        json={"warehouse_codes": ["WH-01", "WH-02"], "hospital_codes": ["HOSP-01", "HOSP-02"]},
    )
    assert subset_res.status_code == 200
    assert len(subset_res.json()["warehouse_utilization"]) == 2
    assert len(subset_res.json()["hospital_summary"]) == 2

    bad_wh_res = client.post(
        "/api/optimization/priority",
        json={"warehouse_codes": ["WH-DOES-NOT-EXIST"]},
    )
    assert bad_wh_res.status_code == 400

    # Verify original inventory and demand records were NEVER mutated by solving
    inv_after = client.get("/api/inventory").json()
    dem_after = client.get("/api/demands").json()
    assert inv_after == inv_before
    assert dem_after == dem_before


def test_scenario_engine_disables_warehouse() -> None:
    net = _sample_shortage_network()
    disrupted = apply_disaster_scenario(
        net,
        DisasterScenarioConfig(name="WH-02 Outage", disabled_warehouses={"WH-02"}),
    )
    assert "WH-02" not in disrupted.warehouses
    outcome = solve_lexicographic_priority_optimization(disrupted)
    assert outcome.total_allocated == 60.0
    assert outcome.tier_unmet_fractions["critical"] == 0.0


def test_shortest_path_respects_closed_corridors() -> None:
    edges = [
        {
            "route_code": "RT-DIRECT",
            "source": "WH-01",
            "target": "HOSP-01",
            "distance_km": 4.0,
            "estimated_travel_time_min": 10.0,
            "is_available": True,
        },
        {
            "route_code": "RT-ALT-1",
            "source": "WH-01",
            "target": "NODE-MID",
            "distance_km": 3.5,
            "estimated_travel_time_min": 9.0,
            "is_available": True,
        },
        {
            "route_code": "RT-ALT-2",
            "source": "NODE-MID",
            "target": "HOSP-01",
            "distance_km": 4.5,
            "estimated_travel_time_min": 11.0,
            "is_available": True,
        },
    ]

    graph_open = build_logistics_graph(edges)
    res_open = compute_shortest_path(graph_open, "WH-01", "HOSP-01", weight="distance_km")
    assert res_open.reachable is True
    assert res_open.total_weight == 4.0

    graph_closed = build_logistics_graph(edges, closed_edge_codes={"RT-DIRECT"})
    res_closed = compute_shortest_path(graph_closed, "WH-01", "HOSP-01", weight="distance_km")
    assert res_closed.reachable is True
    assert res_closed.path_nodes == ["WH-01", "NODE-MID", "HOSP-01"]
    assert res_closed.total_weight == 8.0
