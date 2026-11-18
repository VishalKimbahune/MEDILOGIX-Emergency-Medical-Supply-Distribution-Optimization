"""
Vehicle Routing Problem (VRP) Extension Skeleton (Google OR-Tools).

Decoupled from supply allocation optimization: takes solved warehouse-to-hospital
loads and plans capacitated multi-stop vehicle dispatch routes.

TODO (Next Development Phases):
1. Implement Capacitated VRP (CVRP) using ortools.constraint_solver.routing_enums_pb2
   and pywrapcp.RoutingModel.
2. Support heterogeneous fleet payload limits (kg) per warehouse.
3. Add soft emergency delivery time windows for critical hospitals.
4. Persist solved multi-stop sequences into the Delivery ORM model.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VRPStop:
    """Hospital delivery stop assigned to a warehouse dispatch."""

    hospital_code: str
    demand_weight_kg: float
    priority_level: str = "normal"


@dataclass
class VRPRequestInput:
    """Input payload for single-warehouse Capacitated VRP."""

    warehouse_code: str
    stops: list[VRPStop]
    distance_matrix_km: list[list[float]]
    vehicle_capacities_kg: list[float]


@dataclass
class VRPPlanResult:
    """Structured VRP output (skeleton)."""

    warehouse_code: str
    status: str
    routes: list[dict[str, object]] = field(default_factory=list)
    total_distance_km: float = 0.0
    notes: str = ""


def solve_capacitated_vrp(vrp_input: VRPRequestInput) -> VRPPlanResult:
    """
    Placeholder entry point for Google OR-Tools Capacitated VRP.

    TODO: Replace with full OR-Tools pywrapcp RoutingModel solver once
    distance matrices and vehicle fleet records are finalized.
    """
    return VRPPlanResult(
        warehouse_code=vrp_input.warehouse_code,
        status="NOT_IMPLEMENTED",
        routes=[],
        total_distance_km=0.0,
        notes=(
            "TODO: Capacitated VRP using Google OR-Tools will be implemented in "
            "the routing optimization phase. Allocation LP remains decoupled."
        ),
    )
