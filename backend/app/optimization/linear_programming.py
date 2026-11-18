"""
Shared Linear Programming data structures, validation, and PuLP formulation helpers.

Provides canonical multi-commodity LP inputs, strict input validation,
deterministic CBC solver setup, constraint builders, and post-solve KPI
aggregations shared by transportation.py and priority.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pulp

VALID_PRIORITIES: set[str] = {"critical", "high", "normal"}
PRIORITY_ORDER: tuple[str, str, str] = ("critical", "high", "normal")
SOLVER_DISPLAY_NAME: str = "PuLP CBC (COIN-OR Branch and Cut)"


class OptimizationValidationError(ValueError):
    """Raised when optimization inputs fail mathematical or domain validation."""


@dataclass(frozen=True)
class NetworkOptimizationInput:
    """
    Canonical input representation for multi-commodity medical allocation LP.

    Sets:
        I (warehouses): Active distribution warehouses.
        J (hospitals): Active hospitals partitioned by priority P_j.
        K (products): Essential medical supply items.

    Parameters:
        supply: S_ik >= 0, available stock of product k at warehouse i.
        demand: D_jk >= 0, requested demand of product k at hospital j.
        unit_cost: C_ijk >= 0, unit transportation cost from i to j for product k.
        route_availability: A_ij in {True, False}, route availability between i and j.
        route_capacity_kg: Optional Q_ij > 0 payload limit per route.
        product_weight_kg: Optional w_k > 0 unit weight in kg per product.
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
    # Optional descriptive metadata for rich API responses & UI tables
    warehouse_names: dict[str, str] = field(default_factory=dict)
    hospital_names: dict[str, str] = field(default_factory=dict)
    product_names: dict[str, str] = field(default_factory=dict)
    product_units: dict[str, str] = field(default_factory=dict)
    route_metadata: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)


@dataclass
class OptimizationOutcome:
    """Complete solved output from an Operations Research allocation model."""

    model_type: str
    solver_status: str
    total_cost: float
    total_demand: float
    total_allocated: float
    total_unmet_demand: float
    fulfillment_percentage: float
    execution_time_ms: float
    allocations: list[dict[str, Any]]
    unmet_demands: list[dict[str, Any]]
    tier_unmet_fractions: dict[str, float] = field(default_factory=dict)
    priority_summary: list[dict[str, Any]] = field(default_factory=list)
    warehouse_utilization: list[dict[str, Any]] = field(default_factory=list)
    product_summary: list[dict[str, Any]] = field(default_factory=list)
    hospital_summary: list[dict[str, Any]] = field(default_factory=list)
    stage_results: list[dict[str, Any]] = field(default_factory=list)
    solver_name: str = SOLVER_DISPLAY_NAME
    variable_count: int = 0
    constraint_count: int = 0


def create_cbc_solver() -> pulp.PULP_CBC_CMD:
    """Return a deterministic, silent PuLP CBC solver configuration."""
    return pulp.PULP_CBC_CMD(msg=False, threads=1)


def validate_optimization_input(data: NetworkOptimizationInput) -> None:
    """
    Validate mathematical model sets and parameters prior to invoking the solver.

    Raises:
        OptimizationValidationError: If required sets are empty or numeric parameters are invalid.
    """
    if not data.warehouses:
        raise OptimizationValidationError("At least one active warehouse is required for optimization.")
    if not data.hospitals:
        raise OptimizationValidationError("At least one active hospital is required for optimization.")
    if not data.products:
        raise OptimizationValidationError("At least one medical product is required for optimization.")

    for hosp in data.hospitals:
        prio = data.hospital_priorities.get(hosp, "normal").lower()
        if prio not in VALID_PRIORITIES:
            raise OptimizationValidationError(
                f"Invalid priority '{prio}' for hospital '{hosp}'. Expected critical, high, or normal."
            )

    for (wh, prod), qty in data.supply.items():
        if float(qty) < 0.0:
            raise OptimizationValidationError(
                f"Negative warehouse supply ({qty}) detected for ({wh}, {prod})."
            )

    for (hosp, prod), qty in data.demand.items():
        if float(qty) < 0.0:
            raise OptimizationValidationError(
                f"Negative hospital demand ({qty}) detected for ({hosp}, {prod})."
            )

    for key, cost in data.unit_cost.items():
        if float(cost) < 0.0:
            raise OptimizationValidationError(
                f"Negative transportation cost ({cost}) detected for {key}."
            )

    if data.route_capacity_kg:
        for pair, cap in data.route_capacity_kg.items():
            if float(cap) < 0.0:
                raise OptimizationValidationError(
                    f"Negative route capacity ({cap}) detected for route {pair}."
                )


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

    Constraints enforced:
    1. Warehouse inventory limit:  sum_{j in J} x[i,j,k] <= S[i,k]       forall i, k
    2. Hospital demand balance:    sum_{i in I} x[i,j,k] + u[j,k] == D[j,k]  forall j, k
    3. Route availability:         x[i,j,k] omitted (forced to 0) when A[i,j] == False
    4. Non-negativity:             x[i,j,k] >= 0, u[j,k] >= 0
    5. Optional route capacity:    sum_{k in K} w[k] * x[i,j,k] <= Q[i,j]
    """
    validate_optimization_input(data)

    prob = pulp.LpProblem(problem_name, pulp.LpMinimize)

    # Decision variables x[i,j,k] >= 0 created strictly for available routes (A_ij == True)
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

    # Constraint A: Warehouse inventory limits
    for wh in data.warehouses:
        for prod in data.products:
            available = float(data.supply.get((wh, prod), 0.0))
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

    # Constraint B: Hospital demand balance
    for hosp in data.hospitals:
        for prod in data.products:
            req = float(data.demand.get((hosp, prod), 0.0))
            incoming = [
                x_vars[(wh, hosp, prod)]
                for wh in data.warehouses
                if (wh, hosp, prod) in x_vars
            ]
            prob += (
                pulp.lpSum(incoming) + u_vars[(hosp, prod)] == req,
                f"demand_{hosp}_{prod}".replace("-", "_"),
            )

    # Constraint E (Optional): Route/Vehicle payload weight capacity
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


def _safe_pct(numerator: float, denominator: float) -> float:
    """Compute percentage safely without division-by-zero errors."""
    if denominator <= 0.0:
        return 100.0
    return round((numerator / denominator) * 100.0, 2)


def extract_solution_details(
    data: NetworkOptimizationInput,
    x_vars: dict[tuple[str, str, str], pulp.LpVariable],
    u_vars: dict[tuple[str, str], pulp.LpVariable],
    solver_status: str = "Optimal",
) -> dict[str, Any]:
    """
    Extract allocations, unmet demands, costs, warehouse utilization, product-wise
    summaries, hospital-wise allocations, and priority-tier analytics.

    If solver_status != 'Optimal', returns zero allocations and marks all demand unmet
    so non-optimal or infeasible runs are never misrepresented as valid solutions.
    """
    is_optimal = solver_status == "Optimal"

    allocations: list[dict[str, Any]] = []
    total_cost = 0.0
    total_allocated = 0.0

    wh_allocated: dict[str, float] = {wh: 0.0 for wh in data.warehouses}
    wh_cost: dict[str, float] = {wh: 0.0 for wh in data.warehouses}
    prod_allocated: dict[str, float] = {prod: 0.0 for prod in data.products}
    prod_cost: dict[str, float] = {prod: 0.0 for prod in data.products}
    hosp_allocated: dict[str, float] = {hosp: 0.0 for hosp in data.hospitals}
    hosp_cost: dict[str, float] = {hosp: 0.0 for hosp in data.hospitals}

    if is_optimal:
        for (wh, hosp, prod), var in x_vars.items():
            qty = float(pulp.value(var) or 0.0)
            if qty > 1e-6:
                c_ijk = float(data.unit_cost.get((wh, hosp, prod), 0.0))
                shipment_cost = qty * c_ijk
                total_cost += shipment_cost
                total_allocated += qty
                wh_allocated[wh] += qty
                wh_cost[wh] += shipment_cost
                prod_allocated[prod] += qty
                prod_cost[prod] += shipment_cost
                hosp_allocated[hosp] += qty
                hosp_cost[hosp] += shipment_cost

                route_meta = data.route_metadata.get((wh, hosp), {})
                allocations.append(
                    {
                        "warehouse_code": wh,
                        "warehouse_name": data.warehouse_names.get(wh, wh),
                        "hospital_code": hosp,
                        "hospital_name": data.hospital_names.get(hosp, hosp),
                        "hospital_priority": data.hospital_priorities.get(hosp, "normal").lower(),
                        "product_code": prod,
                        "product_name": data.product_names.get(prod, prod),
                        "product_unit": data.product_units.get(prod, "units"),
                        "quantity_allocated": round(qty, 4),
                        "unit_cost": round(c_ijk, 4),
                        "transport_cost": round(shipment_cost, 2),
                        "route_code": route_meta.get("route_code"),
                        "distance_km": route_meta.get("distance_km"),
                        "estimated_travel_time_min": route_meta.get("estimated_travel_time_min"),
                    }
                )

    allocations.sort(
        key=lambda item: (item["warehouse_code"], item["hospital_code"], item["product_code"])
    )

    unmet_demands: list[dict[str, Any]] = []
    total_demand = 0.0
    total_unmet = 0.0
    tier_unmet: dict[str, float] = {tier: 0.0 for tier in PRIORITY_ORDER}
    tier_requested: dict[str, float] = {tier: 0.0 for tier in PRIORITY_ORDER}
    tier_allocated: dict[str, float] = {tier: 0.0 for tier in PRIORITY_ORDER}
    tier_hospitals: dict[str, set[str]] = {tier: set() for tier in PRIORITY_ORDER}

    prod_demand: dict[str, float] = {prod: 0.0 for prod in data.products}
    prod_unmet: dict[str, float] = {prod: 0.0 for prod in data.products}
    hosp_demand: dict[str, float] = {hosp: 0.0 for hosp in data.hospitals}
    hosp_unmet: dict[str, float] = {hosp: 0.0 for hosp in data.hospitals}

    for hosp in data.hospitals:
        prio = data.hospital_priorities.get(hosp, "normal").lower()
        if prio in tier_hospitals:
            tier_hospitals[prio].add(hosp)

    for (hosp, prod), var in u_vars.items():
        req = float(data.demand.get((hosp, prod), 0.0))
        if is_optimal:
            unmet = max(0.0, float(pulp.value(var) or 0.0))
            if unmet < 1e-6:
                unmet = 0.0
            alloc = max(0.0, req - unmet)
        else:
            unmet = req
            alloc = 0.0

        prio = data.hospital_priorities.get(hosp, "normal").lower()
        total_demand += req
        total_unmet += unmet
        tier_requested[prio] = tier_requested.get(prio, 0.0) + req
        tier_unmet[prio] = tier_unmet.get(prio, 0.0) + unmet
        tier_allocated[prio] = tier_allocated.get(prio, 0.0) + alloc

        prod_demand[prod] += req
        prod_unmet[prod] += unmet
        hosp_demand[hosp] += req
        hosp_unmet[hosp] += unmet

        if req > 0:
            unmet_demands.append(
                {
                    "hospital_code": hosp,
                    "hospital_name": data.hospital_names.get(hosp, hosp),
                    "priority_level": prio,
                    "product_code": prod,
                    "product_name": data.product_names.get(prod, prod),
                    "quantity_requested": round(req, 4),
                    "quantity_allocated": round(alloc, 4),
                    "unmet_quantity": round(unmet, 4),
                }
            )

    unmet_demands.sort(key=lambda item: (item["hospital_code"], item["product_code"]))

    tier_fractions = {
        tier: round(tier_unmet[tier] / tier_requested[tier], 6)
        if tier_requested[tier] > 0.0
        else 0.0
        for tier in PRIORITY_ORDER
    }

    priority_summary = [
        {
            "priority_level": tier,
            "hospital_count": len(tier_hospitals[tier]),
            "total_demand": round(tier_requested[tier], 4),
            "total_allocated": round(tier_allocated[tier], 4),
            "total_unmet": round(tier_unmet[tier], 4),
            "unmet_fraction": tier_fractions[tier],
            "fulfillment_pct": _safe_pct(tier_allocated[tier], tier_requested[tier]),
        }
        for tier in PRIORITY_ORDER
    ]

    warehouse_utilization = []
    for wh in data.warehouses:
        avail_stock = sum(float(data.supply.get((wh, prod), 0.0)) for prod in data.products)
        alloc_out = wh_allocated[wh]
        remaining = max(0.0, avail_stock - alloc_out)
        warehouse_utilization.append(
            {
                "warehouse_code": wh,
                "warehouse_name": data.warehouse_names.get(wh, wh),
                "available_stock": round(avail_stock, 4),
                "allocated_quantity": round(alloc_out, 4),
                "remaining_stock": round(remaining, 4),
                "utilization_pct": round((alloc_out / avail_stock) * 100.0, 2)
                if avail_stock > 0.0
                else 0.0,
                "transport_cost": round(wh_cost[wh], 2),
            }
        )

    product_summary = []
    for prod in data.products:
        total_sup = sum(float(data.supply.get((wh, prod), 0.0)) for wh in data.warehouses)
        dem = prod_demand[prod]
        alloc = prod_allocated[prod]
        unmet = prod_unmet[prod]
        product_summary.append(
            {
                "product_code": prod,
                "product_name": data.product_names.get(prod, prod),
                "unit": data.product_units.get(prod, "units"),
                "total_supply": round(total_sup, 4),
                "total_demand": round(dem, 4),
                "total_allocated": round(alloc, 4),
                "total_unmet": round(unmet, 4),
                "fulfillment_pct": _safe_pct(alloc, dem),
                "transport_cost": round(prod_cost[prod], 2),
            }
        )

    hospital_summary = []
    for hosp in data.hospitals:
        dem = hosp_demand[hosp]
        alloc = hosp_allocated[hosp]
        unmet = hosp_unmet[hosp]
        hospital_summary.append(
            {
                "hospital_code": hosp,
                "hospital_name": data.hospital_names.get(hosp, hosp),
                "priority_level": data.hospital_priorities.get(hosp, "normal").lower(),
                "total_demand": round(dem, 4),
                "total_allocated": round(alloc, 4),
                "total_unmet": round(unmet, 4),
                "fulfillment_pct": _safe_pct(alloc, dem),
                "transport_cost": round(hosp_cost[hosp], 2),
            }
        )

    fulfillment_pct = _safe_pct(total_allocated, total_demand)

    return {
        "allocations": allocations,
        "unmet_demands": unmet_demands,
        "total_cost": round(total_cost, 2),
        "total_demand": round(total_demand, 4),
        "total_allocated": round(total_allocated, 4),
        "total_unmet_demand": round(total_unmet, 4),
        "fulfillment_percentage": fulfillment_pct,
        "tier_unmet_fractions": tier_fractions,
        "priority_summary": priority_summary,
        "warehouse_utilization": warehouse_utilization,
        "product_summary": product_summary,
        "hospital_summary": hospital_summary,
    }
