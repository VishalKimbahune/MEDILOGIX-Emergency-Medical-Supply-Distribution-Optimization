"""
Multi-Commodity Transportation Problem Solver (PuLP CBC).

Decision variables:
    x[i,j,k] >= 0 : quantity of product k transported from warehouse i to hospital j.
    u[j,k]   >= 0 : unmet demand for product k at hospital j.

Formulation:
    When allow_unmet_demand=True (default for emergency networks that may face shortages):
      - Stage 1 (Network Fulfillment): Minimize total aggregate unmet demand sum_{j,k} u[j,k]
        without priority weighting (all hospitals treated equally).
      - Stage 2 (Cost Minimization): Lock optimal aggregate unmet demand U* and minimize
        total transportation cost sum_{i,j,k} c[i,j,k] * x[i,j,k].

    When allow_unmet_demand=False (strict full-demand transportation LP):
      - Single-stage minimization of total transportation cost with u[j,k] == 0.
        Reports 'Infeasible' cleanly if aggregate supply or route connectivity cannot
        satisfy all hospital demands.
"""

from __future__ import annotations

import time
from typing import Any

import pulp

from app.optimization.linear_programming import (
    SOLVER_DISPLAY_NAME,
    NetworkOptimizationInput,
    OptimizationOutcome,
    build_base_allocation_lp,
    create_cbc_solver,
    extract_solution_details,
)

SHORTAGE_LOCK_TOLERANCE: float = 1e-6


def solve_transportation_problem(
    data: NetworkOptimizationInput,
    allow_unmet_demand: bool = True,
) -> OptimizationOutcome:
    """
    Solve the multi-commodity medical supply transportation LP via PuLP CBC.

    Args:
        data: Canonical network supply, demand, cost, and route availability inputs.
        allow_unmet_demand: If True, allows u[j,k] >= 0 and minimizes total unmet demand
            before minimizing transportation cost (priority-neutral). If False, enforces
            strict demand satisfaction u[j,k] == 0 and reports Infeasible on shortages.

    Returns:
        OptimizationOutcome with solver status, stage diagnostics, optimal allocations, and KPIs.
    """
    start_time = time.perf_counter()

    prob, x_vars, u_vars = build_base_allocation_lp(
        problem_name="MEDILOGIX_Multi_Commodity_Transportation",
        data=data,
        allow_unmet_demand=allow_unmet_demand,
    )
    solver = create_cbc_solver()
    stage_results: list[dict[str, Any]] = []
    solver_status = "Not Solved"

    transport_cost_expr = pulp.lpSum(
        float(data.unit_cost.get((wh, hosp, prod), 0.0)) * var
        for (wh, hosp, prod), var in x_vars.items()
    )

    if allow_unmet_demand:
        # Stage 1: Minimize aggregate unmet demand (priority-neutral)
        s1_start = time.perf_counter()
        total_unmet_expr = pulp.lpSum(u_vars.values())
        prob.setObjective(total_unmet_expr)
        status_code = prob.solve(solver)
        solver_status = pulp.LpStatus.get(status_code, "Unknown")
        s1_ms = round((time.perf_counter() - s1_start) * 1000.0, 2)

        if solver_status == "Optimal":
            optimal_unmet = max(0.0, float(pulp.value(total_unmet_expr) or 0.0))
            stage_results.append(
                {
                    "stage": 1,
                    "name": "Aggregate Unmet Demand Minimization (Priority-Neutral)",
                    "priority_tier": "all",
                    "objective_metric": "total_unmet_units",
                    "objective_value": round(optimal_unmet, 4),
                    "solver_status": solver_status,
                    "execution_time_ms": s1_ms,
                    "skipped": False,
                }
            )
            upper_bound = 0.0 if optimal_unmet <= 1e-9 else optimal_unmet + SHORTAGE_LOCK_TOLERANCE
            prob += (
                total_unmet_expr <= upper_bound,
                "lock_stage_1_aggregate_unmet_demand",
            )

            # Stage 2: Minimize total transportation cost while preserving maximum fulfillment
            s2_start = time.perf_counter()
            prob.setObjective(transport_cost_expr)
            status_code = prob.solve(solver)
            solver_status = pulp.LpStatus.get(status_code, "Unknown")
            s2_ms = round((time.perf_counter() - s2_start) * 1000.0, 2)
            opt_cost = (
                round(float(pulp.value(transport_cost_expr) or 0.0), 2)
                if solver_status == "Optimal"
                else None
            )
            stage_results.append(
                {
                    "stage": 2,
                    "name": "Total Transportation Cost Minimization",
                    "priority_tier": "cost",
                    "objective_metric": "total_transport_cost_inr",
                    "objective_value": opt_cost,
                    "solver_status": solver_status,
                    "execution_time_ms": s2_ms,
                    "skipped": False,
                }
            )
        else:
            stage_results.append(
                {
                    "stage": 1,
                    "name": "Aggregate Unmet Demand Minimization (Priority-Neutral)",
                    "priority_tier": "all",
                    "objective_metric": "total_unmet_units",
                    "objective_value": None,
                    "solver_status": solver_status,
                    "execution_time_ms": s1_ms,
                    "skipped": False,
                }
            )
    else:
        # Strict single-stage transportation LP (u[j,k] == 0)
        s1_start = time.perf_counter()
        prob.setObjective(transport_cost_expr)
        status_code = prob.solve(solver)
        solver_status = pulp.LpStatus.get(status_code, "Unknown")
        s1_ms = round((time.perf_counter() - s1_start) * 1000.0, 2)
        opt_cost = (
            round(float(pulp.value(transport_cost_expr) or 0.0), 2)
            if solver_status == "Optimal"
            else None
        )
        stage_results.append(
            {
                "stage": 1,
                "name": "Strict Full-Fulfillment Transportation Cost Minimization",
                "priority_tier": "cost",
                "objective_metric": "total_transport_cost_inr",
                "objective_value": opt_cost,
                "solver_status": solver_status,
                "execution_time_ms": s1_ms,
                "skipped": False,
            }
        )

    elapsed_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
    details = extract_solution_details(data, x_vars, u_vars, solver_status=solver_status)

    return OptimizationOutcome(
        model_type="transportation_lp",
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
