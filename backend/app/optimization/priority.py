"""
Lexicographic Priority-Based Shortage Optimization (PuLP).

Implements a strict 4-stage lexicographic optimization sequence:
  Stage 1: Minimize critical hospital unmet-demand fraction (F_critical).
  Stage 2: Minimize high-priority hospital unmet-demand fraction (F_high)
           while locking F_critical <= F_critical* + eps.
  Stage 3: Minimize normal-priority hospital unmet-demand fraction (F_normal)
           while locking F_critical* and F_high*.
  Stage 4: Minimize total transportation cost while preserving all three
           optimal unmet-demand tier fractions.

TODO (Future Phases):
- Add equity/minimax fairness constraints across hospitals within the same tier.
- Add product-criticality weights (e.g., Oxygen Cylinders vs. general supplies).
- Support sensitivity analysis reporting (dual prices / reduced costs).
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

LEXICOGRAPHIC_TOLERANCE: float = 1e-8


def _tier_unmet_fraction_expr(
    tier: str,
    data: NetworkOptimizationInput,
    u_vars: dict[tuple[str, str], pulp.LpVariable],
) -> tuple[pulp.LpAffineExpression | None, float]:
    """Build linear expression for the aggregate unmet-demand fraction of a priority tier."""
    tier_hospitals = [
        hosp
        for hosp in data.hospitals
        if data.hospital_priorities.get(hosp, "normal").lower() == tier
    ]
    total_tier_demand = sum(
        max(0.0, float(data.demand.get((hosp, prod), 0.0)))
        for hosp in tier_hospitals
        for prod in data.products
    )
    if total_tier_demand <= 0.0:
        return None, 0.0

    unmet_sum = pulp.lpSum(
        u_vars[(hosp, prod)]
        for hosp in tier_hospitals
        for prod in data.products
    )
    return unmet_sum / total_tier_demand, total_tier_demand


def solve_lexicographic_priority_optimization(
    data: NetworkOptimizationInput,
    tolerance: float = LEXICOGRAPHIC_TOLERANCE,
) -> OptimizationOutcome:
    """
    Solve the 4-stage lexicographic priority shortage optimization model.

    Guarantees mathematically that higher-priority hospital demand is never
    sacrificed to reduce transportation costs or fulfill lower-priority tiers.
    """
    start_time = time.perf_counter()

    prob, x_vars, u_vars = build_base_allocation_lp(
        problem_name="MEDILOGIX_Lexicographic_Priority_LP",
        data=data,
        allow_unmet_demand=True,
    )
    solver = pulp.PULP_CBC_CMD(msg=False)
    solver_status = "Not Solved"

    # Stages 1, 2, 3: Minimize unmet-demand fraction by priority tier
    for stage_idx, tier in enumerate(("critical", "high", "normal"), start=1):
        tier_expr, total_tier_demand = _tier_unmet_fraction_expr(tier, data, u_vars)
        if tier_expr is None or total_tier_demand <= 0.0:
            continue

        prob.setObjective(tier_expr)
        status_code = prob.solve(solver)
        solver_status = pulp.LpStatus.get(status_code, "Unknown")
        if solver_status != "Optimal":
            break

        optimal_fraction = max(0.0, float(pulp.value(tier_expr) or 0.0))
        # Lock exact zero when tier is fully satisfied so Stage 4 never trades away
        # critical demand up to tolerance to shave transport cost.
        upper_bound = 0.0 if optimal_fraction <= 1e-9 else optimal_fraction + tolerance
        prob += (
            tier_expr <= upper_bound,
            f"lock_stage_{stage_idx}_{tier}_unmet_fraction",
        )

    # Stage 4: Minimize total transportation cost subject to locked tier objectives
    if solver_status in {"Optimal", "Not Solved"}:
        transport_cost_expr = pulp.lpSum(
            float(data.unit_cost.get((wh, hosp, prod), 0.0)) * var
            for (wh, hosp, prod), var in x_vars.items()
        )
        prob.setObjective(transport_cost_expr)
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
        model_type="lexicographic_priority",
        solver_status=solver_status,
        total_cost=total_cost,
        total_allocated=total_allocated,
        total_unmet_demand=total_unmet,
        execution_time_ms=elapsed_ms,
        allocations=allocations,
        unmet_demands=unmet_demands,
        tier_unmet_fractions=tier_fractions,
    )
