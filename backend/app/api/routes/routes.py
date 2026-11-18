"""Delivery Routes & Graph Routing API routes (/api/routes)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.hospital import Hospital
from app.models.road import Road
from app.models.warehouse import Warehouse
from app.optimization.shortest_path import build_logistics_graph, compute_shortest_path
from app.optimization.vehicle_routing import VRPRequestInput, solve_capacitated_vrp

router = APIRouter(prefix="/api/routes", tags=["Routes"])


class ShortestPathRequest(BaseModel):
    source_code: str = Field(..., examples=["WH-01"])
    target_code: str = Field(..., examples=["HOSP-01"])
    weight_metric: Literal["distance_km", "estimated_travel_time_min"] = "distance_km"
    closed_route_codes: list[str] = Field(default_factory=list)


@router.get("")
def list_routes(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    """List all warehouse-to-hospital road corridors with synthetic estimates."""
    warehouses = {w.id: w for w in db.scalars(select(Warehouse)).all()}
    hospitals = {h.id: h for h in db.scalars(select(Hospital)).all()}
    roads = list(db.scalars(select(Road).order_by(Road.route_code)).all())

    return [
        {
            "id": r.id,
            "route_code": r.route_code,
            "warehouse_id": r.warehouse_id,
            "warehouse_code": warehouses[r.warehouse_id].code if r.warehouse_id in warehouses else None,
            "hospital_id": r.hospital_id,
            "hospital_code": hospitals[r.hospital_id].code if r.hospital_id in hospitals else None,
            "distance_km": r.distance_km,
            "estimated_travel_time_min": r.estimated_travel_time_min,
            "base_transport_cost_per_unit": r.base_transport_cost_per_unit,
            "is_available": r.is_available,
            "road_condition": r.road_condition,
            "data_note": r.data_note,
        }
        for r in roads
    ]


@router.post("/shortest-path")
def shortest_path_lookup(
    payload: ShortestPathRequest, db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Compute shortest path over the current corridor graph via NetworkX Dijkstra."""
    warehouses = {w.id: w.code for w in db.scalars(select(Warehouse)).all()}
    hospitals = {h.id: h.code for h in db.scalars(select(Hospital)).all()}
    roads = list(db.scalars(select(Road)).all())

    edges = [
        {
            "route_code": r.route_code,
            "source": warehouses[r.warehouse_id],
            "target": hospitals[r.hospital_id],
            "distance_km": r.distance_km,
            "estimated_travel_time_min": r.estimated_travel_time_min,
            "is_available": r.is_available,
        }
        for r in roads
        if r.warehouse_id in warehouses and r.hospital_id in hospitals
    ]

    graph = build_logistics_graph(edges, closed_edge_codes=set(payload.closed_route_codes))
    result = compute_shortest_path(
        graph,
        source=payload.source_code,
        target=payload.target_code,
        weight=payload.weight_metric,
    )
    return result.__dict__


@router.post("/vrp")
def run_vrp_placeholder(warehouse_code: str = "WH-01") -> dict[str, Any]:
    """Skeleton endpoint for Google OR-Tools Capacitated VRP (TODO)."""
    vrp_result = solve_capacitated_vrp(
        VRPRequestInput(
            warehouse_code=warehouse_code,
            stops=[],
            distance_matrix_km=[],
            vehicle_capacities_kg=[],
        )
    )
    return vrp_result.__dict__
