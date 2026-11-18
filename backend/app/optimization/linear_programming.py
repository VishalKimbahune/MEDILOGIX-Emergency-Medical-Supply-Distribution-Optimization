"""
Shared Linear Programming data structures and PuLP formulation helpers.

Provides reusable LP inputs, decision-variable creation, and core constraint
builders shared by transportation.py and priority.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pulp


@dataclass(frozen=True)
class NetworkOptimizationInput:
    """
    Canonical input representation for multi-commodity medical allocation LP.

    Attributes:
        warehouses: List of active warehouse identifiers i in I.
        hospitals: List of hospital identifiers j in J.
        products: List of medical product identifiers k in K.
        hospital_priorities: Mapping hospital_id -> 'critical' | 'high' | 'normal'.
        supply: Mapping (warehouse_id, product_id) -> available stock S[i,k] >= 0.
        demand: Mapping (hospital_id, product_id) -> requested demand D[j,k] >= 0.
        unit_cost: Mapping (warehouse_id, hospital_id, product_id) -> unit shipping cost c[i,j,k].
        route_availability: Mapping (warehouse_id, hospital_id) -> bool (True if corridor is open).
        route_capacity_kg: Optional mapping (warehouse_id, hospital_id) -> max payload weight.
        product_weight_kg: Optional mapping product_id -> unit weight in kg.
    """

    warehouses: list[str]
    hospitals: list[str]
    products: list[str]
    hospital_priorities: dict[str, str]
    supply: dict[tuple[str, str], float]
    demand: dict[tuple[str, str], float]
    unit_cost: dict[tuple[str, str, str], float]
    route_availability: dict[tuple[str, str], bool] = field(default_factory=dict)
    route_capacity_kg: dict[tuple[str, str], float] | None = None
    product_weight_kg: dict[str, float] | None = None


@dataclass
class OptimizationOutcome:
    """Solved output from an Operations Research allocation model."""

    model_type: str
    solver_status: str
    total_cost: float
    total_allocated: float
    total_unmet_demand: float
    execution_time_ms: float
    allocations: list[dict[str, Any]]
    unmet_demands: list[dict[str, Any]]
    tier_unmet_fractions: dict[str, float] = field(default_factory=dict)


def build_base_allocation_lp(
    problem_name: str,
    data: NetworkOptimizationInput,
    allow_unmet_demand: bool = True,
) -> tuple[
    pulp.LpProblem,
    dict[tuple[str, str, str], pulp.LpVariable],
    dict[tuple[str, str], pulp.LpVariable],
]:
    """
    Construct a base PuLP LP model with variables x[i,j,k], u[j,k] and core constraints.

    Constraints added:
    1. Warehouse stock balance: sum_j x[i,j,k] <= S[i,k]
    2. Hospital demand balance: sum_i x[i,j,k] + u[j,k] == D[j,k]
    3. Route availability: x[i,j,k] == 0 if route (i,j) is unavailable
    4. Optional route payload capacity: sum_k w[k] * x[i,j,k] <= Q[i,j]
    """
    prob = pulp.LpProblem(problem_name, pulp.LpMinimize)

    # Decision variables x[i,j,k] >= 0 for available routes
    x_vars: dict[tuple[str, str, str], pulp.LpVariable] = {}
    for wh in data.warehouses:
        for hosp in data.hospitals:
            is_open = data.route_availability.get((wh, hosp), True)
            if not is_open:
                continue
            for prod in data.products:
                var_name = f"x_{wh}_{hosp}_{prod}".replace("-", "_")
                x_vars[(wh, hosp, prod)] = pulp.LpVariable(var_name, lowBound=0.0, cat="Continuous")

    # Unmet demand variables u[j,k] >= 0
    u_vars: dict[tuple[str, str], pulp.LpVariable] = {}
    for hosp in data.hospitals:
        for prod in data.products:
            var_name = f"u_{hosp}_{prod}".replace("-", "_")
            upper = None if allow_unmet_demand else 0.0
            u_vars[(hosp, prod)] = pulp.LpVariable(
                var_name, lowBound=0.0, upBound=upper, cat="Continuous"
            )

    # Constraint 1: Warehouse stock limits
    for wh in data.warehouses:
        for prod in data.products:
            available = max(0.0, float(data.supply.get((wh, prod), 0.0)))
            outgoing = [
                x_vars[(wh, hosp, prod)]
                for hosp in data.hospitals
                if (wh, hosp, prod) in x_vars
            ]
            if outgoing:
                prob += (
                    pulp.lpSum(outgoing) <= available,
                    f"stock_{wh}_{prod}".replace("-", "_"),
                )

    # Constraint 2: Hospital demand balance
    for hosp in data.hospitals:
        for prod in data.products:
            req = max(0.0, float(data.demand.get((hosp, prod), 0.0)))
            incoming = [
                x_vars[(wh, hosp, prod)]
                for wh in data.warehouses
                if (wh, hosp, prod) in x_vars
            ]
            prob += (
                pulp.lpSum(incoming) + u_vars[(hosp, prod)] == req,
                f"demand_{hosp}_{prod}".replace("-", "_"),
            )

    # Constraint 4 (Optional): Route/Vehicle payload weight limits
    if data.route_capacity_kg and data.product_weight_kg:
        for (wh, hosp), max_kg in data.route_capacity_kg.items():
            terms = [
                float(data.product_weight_kg.get(prod, 1.0)) * x_vars[(wh, hosp, prod)]
                for prod in data.products
                if (wh, hosp, prod) in x_vars
            ]
            if terms:
                prob += (
                    pulp.lpSum(terms) <= float(max_kg),
                    f"capacity_{wh}_{hosp}".replace("-", "_"),
                )

    return prob, x_vars, u_vars


def extract_solution_details(
    data: NetworkOptimizationInput,
    x_vars: dict[tuple[str, str, str], pulp.LpVariable],
    u_vars: dict[tuple[str, str], pulp.LpVariable],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], float, float, float, dict[str, float]]:
    """Extract allocations, unmet demands, costs, and priority-tier unmet fractions."""
    allocations: list[dict[str, Any]] = []
    total_cost = 0.0
    total_allocated = 0.0

    for (wh, hosp, prod), var in x_vars.items():
        qty = float(pulp.value(var) or 0.0)
        if qty > 1e-6:
            c_ijk = float(data.unit_cost.get((wh, hosp, prod), 0.0))
            shipment_cost = round(qty * c_ijk, 4)
            total_cost += shipment_cost
            total_allocated += qty
            allocations.append(
                {
                    "warehouse_code": wh,
                    "hospital_code": hosp,
                    "product_code": prod,
                    "quantity_allocated": round(qty, 4),
                    "unit_cost": round(c_ijk, 4),
                    "transport_cost": round(shipment_cost, 2),
                }
            )

    unmet_demands: list[dict[str, Any]] = []
    total_unmet = 0.0
    tier_unmet: dict[str, float] = {"critical": 0.0, "high": 0.0, "normal": 0.0}
    tier_requested: dict[str, float] = {"critical": 0.0, "high": 0.0, "normal": 0.0}

    for (hosp, prod), var in u_vars.items():
        req = max(0.0, float(data.demand.get((hosp, prod), 0.0)))
        unmet = max(0.0, float(pulp.value(var) or 0.0))
        alloc = max(0.0, req - unmet)
        prio = data.hospital_priorities.get(hosp, "normal").lower()
        tier_requested[prio] = tier_requested.get(prio, 0.0) + req
        tier_unmet[prio] = tier_unmet.get(prio, 0.0) + unmet
        total_unmet += unmet

        if req > 0:
            unmet_demands.append(
                {
                    "hospital_code": hosp,
                    "priority_level": prio,
                    "product_code": prod,
                    "quantity_requested": round(req, 4),
                    "quantity_allocated": round(alloc, 4),
                    "unmet_quantity": round(unmet, 4),
                }
            )

    tier_fractions = {
        tier: round(tier_unmet[tier] / tier_requested[tier], 6)
        if tier_requested[tier] > 0
        else 0.0
        for tier in ("critical", "high", "normal")
    }

    return (
        allocations,
        unmet_demands,
        round(total_cost, 2),
        round(total_allocated, 4),
        round(total_unmet, 4),
        tier_fractions,
    )
