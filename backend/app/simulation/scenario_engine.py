"""
Disaster & Disruption Scenario Simulation Engine (Phase 4C).

Applies isolated, reproducible emergency perturbations to a baseline
NetworkOptimizationInput without mutating any live database records:
- Warehouse outage (disables warehouse supply & all outgoing corridors)
- Road corridor closure (marks corridors unavailable for LP & OR-Tools VRP)
- Hospital demand spike (increases demand at selected hospitals by a configurable %)
- Vehicle unavailability (tracked in config and enforced in Phase 4A VRP)
- Combined multi-factor disruptions
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.optimization.linear_programming import NetworkOptimizationInput


@dataclass
class DisasterScenarioConfig:
    """Parameters defining a reproducible simulated logistics disruption."""

    name: str
    disabled_warehouses: set[str] = field(default_factory=set)
    closed_routes: set[tuple[str, str]] = field(default_factory=set)
    demand_multiplier: float = 1.0
    supply_multiplier: float = 1.0
    demand_spike_hospitals: set[str] = field(default_factory=set)
    demand_spike_pct: float = 0.0
    disabled_vehicles: set[str] = field(default_factory=set)


def apply_disaster_scenario(
    baseline: NetworkOptimizationInput,
    scenario: DisasterScenarioConfig,
) -> NetworkOptimizationInput:
    """
    Return an isolated NetworkOptimizationInput reflecting all configured
    disruptions without mutating the baseline input or database state.
    """
    active_warehouses = [
        wh for wh in baseline.warehouses if wh not in scenario.disabled_warehouses
    ]

    adjusted_supply = {
        (wh, prod): round(max(0.0, qty * scenario.supply_multiplier), 4)
        for (wh, prod), qty in baseline.supply.items()
        if wh not in scenario.disabled_warehouses
    }

    spike_factor = 1.0 + max(0.0, float(scenario.demand_spike_pct)) / 100.0
    apply_spike_to_all = (
        scenario.demand_spike_pct > 0.0 and len(scenario.demand_spike_hospitals) == 0
    )

    adjusted_demand: dict[tuple[str, str], float] = {}
    for (hosp, prod), qty in baseline.demand.items():
        eff_mult = float(scenario.demand_multiplier)
        if apply_spike_to_all or hosp in scenario.demand_spike_hospitals:
            eff_mult *= spike_factor
        adjusted_demand[(hosp, prod)] = round(max(0.0, qty * eff_mult), 4)

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
        warehouse_names=dict(baseline.warehouse_names),
        hospital_names=dict(baseline.hospital_names),
        product_names=dict(baseline.product_names),
        product_units=dict(baseline.product_units),
        route_metadata=dict(baseline.route_metadata),
    )
