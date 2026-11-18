"""
Disaster Scenario Simulator Engine for MEDILOGIX.

Applies controlled emergency disruptions to a baseline NetworkOptimizationInput
before invoking the Operations Research solvers:
- Warehouse outage / partial capacity degradation
- Road corridor closure (e.g., urban flooding or highway blockage)
- Hospital demand surge (e.g., mass-casualty incident or respiratory spike)

TODO (Future Phases):
- Support baseline vs. disrupted side-by-side comparison reports.
- Support stochastic Monte Carlo disruption batches.
- Persist scenario comparison snapshots in OptimizationRun.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.optimization.linear_programming import NetworkOptimizationInput


@dataclass
class DisasterScenarioConfig:
    """Parameters defining a simulated logistics disruption."""

    name: str
    disabled_warehouses: set[str] = field(default_factory=set)
    closed_routes: set[tuple[str, str]] = field(default_factory=set)
    demand_multiplier: float = 1.0
    supply_multiplier: float = 1.0


def apply_disaster_scenario(
    baseline: NetworkOptimizationInput,
    scenario: DisasterScenarioConfig,
) -> NetworkOptimizationInput:
    """
    Return a new NetworkOptimizationInput reflecting the specified disruption
    without mutating the baseline dataset.
    """
    active_warehouses = [
        wh for wh in baseline.warehouses if wh not in scenario.disabled_warehouses
    ]

    adjusted_supply = {
        (wh, prod): round(max(0.0, qty * scenario.supply_multiplier), 4)
        for (wh, prod), qty in baseline.supply.items()
        if wh not in scenario.disabled_warehouses
    }

    adjusted_demand = {
        (hosp, prod): round(max(0.0, qty * scenario.demand_multiplier), 4)
        for (hosp, prod), qty in baseline.demand.items()
    }

    adjusted_availability = dict(baseline.route_availability)
    for wh in baseline.warehouses:
        for hosp in baseline.hospitals:
            if wh in scenario.disabled_warehouses or (wh, hosp) in scenario.closed_routes:
                adjusted_availability[(wh, hosp)] = False

    return NetworkOptimizationInput(
        warehouses=active_warehouses,
        hospitals=list(baseline.hospitals),
        products=list(baseline.products),
        hospital_priorities=dict(baseline.hospital_priorities),
        supply=adjusted_supply,
        demand=adjusted_demand,
        unit_cost=dict(baseline.unit_cost),
        route_availability=adjusted_availability,
        route_capacity_kg=(
            dict(baseline.route_capacity_kg) if baseline.route_capacity_kg else None
        ),
        product_weight_kg=(
            dict(baseline.product_weight_kg) if baseline.product_weight_kg else None
        ),
    )
