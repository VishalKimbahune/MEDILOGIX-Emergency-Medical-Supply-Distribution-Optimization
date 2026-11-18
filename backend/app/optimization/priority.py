"""
Sequential Lexicographic Priority-Based Shortage Optimization (PuLP CBC).

Implements a strict 4-stage lexicographic optimization sequence without
arbitrary weighted penalties:
  Stage 1: Minimize normalized unmet-demand fraction for Critical hospitals (F_critical).
  Stage 2: Preserve optimal Stage 1 result and minimize normalized unmet-demand
           fraction for High-priority hospitals (F_high).
  Stage 3: Preserve Stages 1 & 2 optimums and minimize normalized unmet-demand
           fraction for Normal-priority hospitals (F_normal).
  Stage 4: Preserve all three priority-tier optimums and minimize total
           transportation cost.

Handles zero-demand priority tiers cleanly (avoiding division by zero) and
records per-stage objective values, solver statuses, and timings for academic
explainability.
"""

from __future__ import annotations

import time
from typing import Any

import pulp

from app.optimization.linear_programming import (
    PRIORITY_ORDER,
    SOLVER_DISPLAY_NAME,
    NetworkOptimizationInput,
    OptimizationOutcome,
    build_base_allocation_lp,
    create_cbc_solver,
    extract_solution_details,
)

LEXICOGRAPHIC_TOLERANCE: float = 1e-8

STAGE_TITLES: dict[str, str] = {
    "critical": "Stage 1: Minimize Critical Hospital Normalized Unmet Demand",
    "high": "Stage 2: Minimize High-Priority Hospital Normalized Unmet Demand",
    "normal": "Stage 3: Minimize Normal-Priority Hospital Normalized Unmet Demand",
}


def _tier_unmet_fraction_expr(
    tier: str,
    data: NetworkOptimizationInput,
    u_vars: dict[tuple[str, str], pulp.LpVariable],
) -> tuple[pulp.LpAffineExpression | None, float]:
    """
    Build linear expression for normalized unmet-demand fraction of a priority tier.

    Returns (None, 0.0) when total tier demand is zero to prevent division by zero.
    """
    tier_hospitals = [
        hosp
        for hosp in data.hospitals
        if data.hospital_priorities.get(hosp, "normal").lower() == tier
    ]
    total_tier_demand = sum(
        float(data.demand.get((hosp, prod), 0.0))
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
    Solve the 4-stage sequential lexicographic priority shortage optimization model.

    Guarantees mathematically that higher-priority hospital demand is never
    sacrificed to reduce transportation costs or fulfill lower-priority tiers.
    """
    start_time = time.perf_counter()

    prob, x_vars, u_vars = build_base_allocation_lp(
        problem_name="MEDILOGIX_Lexicographic_Priority_LP",
        data=data,
        allow_unmet_demand=True,
    )
    solver = create_cbc_solver()
    solver_status = "Not Solved"
    stage_results: list[dict[str, Any]] = []
    aborted = False

    # Stages 1, 2, 3: Sequential normalized unmet-demand minimization by priority tier
    for stage_idx, tier in enumerate(PRIORITY_ORDER, start=1):
        stage_start = time.perf_counter()
        tier_expr, total_tier_demand = _tier_unmet_fraction_expr(tier, data, u_vars)

        if tier_expr is None or total_tier_demand <= 0.0:
            stage_results.append(
                {
                    "stage": stage_idx,
                    "name": STAGE_TITLES[tier],
                    "priority_tier": tier,
                    "objective_metric": f"{tier}_unmet_fraction",
                    "objective_value": 0.0,
                    "tier_demand": 0.0,
                    "solver_status": "Skipped (Zero Demand)",
                    "execution_time_ms": 0.0,
                    "skipped": True,
                }
            )
            continue

        prob.setObjective(tier_expr)
        status_code = prob.solve(solver)
        solver_status = pulp.LpStatus.get(status_code, "Unknown")
        stage_ms = round((time.perf_counter() - stage_start) * 1000.0, 2)

        if solver_status != "Optimal":
            stage_results.append(
                {
                    "stage": stage_idx,
                    "name": STAGE_TITLES[tier],
                    "priority_tier": tier,
                    "objective_metric": f"{tier}_unmet_fraction",
                    "objective_value": None,
                    "tier_demand": round(total_tier_demand, 4),
                    "solver_status": solver_status,
                    "execution_time_ms": stage_ms,
                    "skipped": False,
                }
            )
            aborted = True
            break

        optimal_fraction = max(0.0, float(pulp.value(tier_expr) or 0.0))
        if optimal_fraction <= 1e-9:
            optimal_fraction = 0.0

        stage_results.append(
            {
                "stage": stage_idx,
                "name": STAGE_TITLES[tier],
                "priority_tier": tier,
                "objective_metric": f"{tier}_unmet_fraction",
                "objective_value": round(optimal_fraction, 6),
                "tier_demand": round(total_tier_demand, 4),
                "solver_status": solver_status,
                "execution_time_ms": stage_ms,
                "skipped": False,
            }
        )

        # Lock optimal tier fraction before proceeding to next lexicographic stage.
        # Exact zero bound prevents Stage 4 from trading critical demand up to tolerance.
        upper_bound = 0.0 if optimal_fraction == 0.0 else optimal_fraction + tolerance
        prob += (
            tier_expr <= upper_bound,
            f"lock_stage_{stage_idx}_{tier}_unmet_fraction",
        )

    # Stage 4: Minimize total transportation cost while preserving locked priority optimums
    if not aborted:
        stage4_start = time.perf_counter()
        transport_cost_expr = pulp.lpSum(
            float(data.unit_cost.get((wh, hosp, prod), 0.0)) * var
            for (wh, hosp, prod), var in x_vars.items()
        )
        prob.setObjective(transport_cost_expr)
        status_code = prob.solve(solver)
        solver_status = pulp.LpStatus.get(status_code, "Unknown")
        stage4_ms = round((time.perf_counter() - stage4_start) * 1000.0, 2)
        opt_cost = (
            round(float(pulp.value(transport_cost_expr) or 0.0), 2)
            if solver_status == "Optimal"
            else None
        )
        stage_results.append(
            {
                "stage": 4,
                "name": "Stage 4: Minimize Total Transportation Cost",
                "priority_tier": "cost",
                "objective_metric": "total_transport_cost_inr",
                "objective_value": opt_cost,
                "solver_status": solver_status,
                "execution_time_ms": stage4_ms,
                "skipped": False,
            }
        )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    details = extract_solution_details(data, x_vars, u_vars, solver_status=solver_status)

    return OptimizationOutcome(
        model_type="lexicographic_priority",
        solver_status=solver_status,
        total_cost=details["total_cost"],
        total_demand=details["total_demand"],
        total_allocated=details["total_allocated"],
        total_unmet_demand=details["total_unmet_demand"],
        fulfillment_percentage=details["fulfillment_percentage"],
        execution_time_ms=elapsed_ms,
        allocations=details["allocations"],
        unmet_demands=details["unmet_demands"],
        tier_unmet_fractions=details["tier_unmet_fractions"],
        priority_summary=details["priority_summary"],
        warehouse_utilization=details["warehouse_utilization"],
        product_summary=details["product_summary"],
        hospital_summary=details["hospital_summary"],
        stage_results=stage_results,
        solver_name=SOLVER_DISPLAY_NAME,
        variable_count=len(x_vars) + len(u_vars),
        constraint_count=len(prob.constraints),
    )
