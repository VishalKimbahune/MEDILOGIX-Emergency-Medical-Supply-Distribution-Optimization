"""Unit tests for MEDILOGIX Operations Research optimization modules."""

from __future__ import annotations

from app.optimization.linear_programming import NetworkOptimizationInput
from app.optimization.priority import solve_lexicographic_priority_optimization
from app.optimization.shortest_path import build_logistics_graph, compute_shortest_path
from app.optimization.transportation import solve_transportation_problem
from app.simulation.scenario_engine import DisasterScenarioConfig, apply_disaster_scenario


def _sample_shortage_network() -> NetworkOptimizationInput:
    """
    Create a small controlled-shortage test instance:
    - Total supply of PROD-01 = 100 units
    - Total demand of PROD-01 = 150 units (60 critical + 50 high + 40 normal)
    - Normal hospital is deliberately cheaper to ship to than critical hospital,
      verifying that lexicographic priority optimization protects critical first.
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


def test_transportation_lp_solves_optimally() -> None:
    net = _sample_shortage_network()
    outcome = solve_transportation_problem(net, allow_unmet_demand=True)
    assert outcome.solver_status == "Optimal"
    assert outcome.total_allocated == 100.0
    assert outcome.total_unmet_demand == 50.0
    assert outcome.total_cost > 0.0


def test_lexicographic_priority_protects_critical_hospitals_first() -> None:
    net = _sample_shortage_network()
    outcome = solve_lexicographic_priority_optimization(net)
    assert outcome.solver_status == "Optimal"
    # Critical (60) must be 100% fulfilled (0% unmet fraction)
    assert outcome.tier_unmet_fractions["critical"] == 0.0
    # Remaining 40 units must go to High (50 requested -> 10 unmet = 0.2 fraction)
    assert abs(outcome.tier_unmet_fractions["high"] - 0.2) < 1e-5
    # Normal receives 0 units (100% unmet)
    assert outcome.tier_unmet_fractions["normal"] == 1.0


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
