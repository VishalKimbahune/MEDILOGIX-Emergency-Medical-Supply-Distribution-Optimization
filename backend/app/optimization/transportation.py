"""
Multi-Commodity Transportation Problem Solver (PuLP).

Decision variable:
    x[i,j,k] = quantity of product k transported from warehouse i to hospital j.
    u[j,k]   = unmet demand for product k at hospital j (if shortages exist).

Objective:
    Minimize total transportation cost (plus an optional large shortage penalty
    when allow_unmet_demand=True so available supply is always utilized).

TODO (Future Phases):
- Add integer/batch-size constraints (e.g., pallet or crate rounding).
- Add multi-period rolling-horizon inventory carryover.
- Integrate dynamic fleet capacity coupling with vehicle_routing.py.
"""

from __future__ import annotations

import time

import pulp

from app.optimization.linear_programming import (
    NetworkOptimizationInput,
    OptimizationOutcome,
    build_base_allocation_lp,
    extract_solution_details,
)


def solve_transportation_problem(
    data: NetworkOptimizationInput,
    allow_unmet_demand: bool = True,
    shortage_penalty_multiplier: float = 1000.0,
) -> OptimizationOutcome:
    """
    Solve the multi-commodity medical supply transportation problem via PuLP CBC.

    Args:
        data: Canonical network supply, demand, cost, and route availability inputs.
        allow_unmet_demand: If True, allows u[j,k] >= 0 with a high penalty so
            the model remains feasible under controlled supply shortages.
        shortage_penalty_multiplier: Multiplier applied above maximum unit transport
            cost to penalize unmet demand relative to shipping cost.

    Returns:
        OptimizationOutcome with solver status, optimal allocations, and KPIs.
    """
    start_time = time.perf_counter()

    prob, x_vars, u_vars = build_base_allocation_lp(
        problem_name="MEDILOGIX_Multi_Commodity_Transportation",
        data=data,
        allow_unmet_demand=allow_unmet_demand,
    )

    max_unit_cost = max(data.unit_cost.values(), default=10.0)
    shortage_penalty = max(1000.0, max_unit_cost * shortage_penalty_multiplier)

    transport_cost_expr = pulp.lpSum(
        float(data.unit_cost.get((wh, hosp, prod), 0.0)) * var
        for (wh, hosp, prod), var in x_vars.items()
    )

    if allow_unmet_demand:
        shortage_expr = pulp.lpSum(shortage_penalty * var for var in u_vars.values())
        prob += transport_cost_expr + shortage_expr, "Total_Cost_Plus_Shortage_Penalty"
    else:
        prob += transport_cost_expr, "Total_Transportation_Cost"

    solver = pulp.PULP_CBC_CMD(msg=False)
    status_code = prob.solve(solver)
    solver_status = pulp.LpStatus.get(status_code, "Unknown")
    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    (
        allocations,
        unmet_demands,
        total_cost,
        total_allocated,
        total_unmet,
        tier_fractions,
    ) = extract_solution_details(data, x_vars, u_vars)

    return OptimizationOutcome(
        model_type="transportation_lp",
        solver_status=solver_status,
        total_cost=total_cost,
        total_allocated=total_allocated,
        total_unmet_demand=total_unmet,
        execution_time_ms=elapsed_ms,
        allocations=allocations,
        unmet_demands=unmet_demands,
        tier_unmet_fractions=tier_fractions,
    )
