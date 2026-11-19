"""
Delivery Routes, Fleet Vehicles & Dispatch Management API routes (/api/routes).

Preserves Phase 1-3 corridor listing & NetworkX Dijkstra shortest-path endpoints,
and integrates Phase 4A Google OR-Tools CVRP + Phase 4B Dispatch Management.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.connection import get_db
from app.models.hospital import Hospital
from app.models.road import Road
from app.models.user import User
from app.models.warehouse import Warehouse
from app.optimization.shortest_path import build_logistics_graph, compute_shortest_path
from app.schemas.dispatch import (
    DispatchPlanCreateRequest,
    DispatchPlanDetailResponse,
    DispatchPlanSummaryResponse,
    DispatchStatusUpdateRequest,
    StopStatusUpdateRequest,
    VehicleResponse,
)
from app.services import audit_service, dispatch_service, road_network_service

router = APIRouter(
    prefix="/api/routes",
    tags=["Routes & Dispatch"],
    dependencies=[Depends(require_admin)],
)


class ShortestPathRequest(BaseModel):
    source_code: str = Field(..., examples=["WH-01"])
    target_code: str = Field(..., examples=["HOSP-01"])
    weight_metric: Literal["distance_km", "estimated_travel_time_min"] = "distance_km"
    closed_route_codes: list[str] = Field(default_factory=list)


class OSMShortestPathRequest(BaseModel):
    source_code: str = Field(..., examples=["WH-01"])
    target_code: str = Field(..., examples=["HOSP-01"])
    weight_metric: Literal["distance_km", "estimated_travel_time_min"] = "distance_km"
    closed_way_ids: list[int] = Field(default_factory=list)
    closed_route_codes: list[str] = Field(default_factory=list)
    allow_synthetic_fallback: bool = True


class OSMSyncRequest(BaseModel):
    force_refresh: bool = False


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
            "warehouse_lat": warehouses[r.warehouse_id].latitude if r.warehouse_id in warehouses else None,
            "warehouse_lon": warehouses[r.warehouse_id].longitude if r.warehouse_id in warehouses else None,
            "hospital_id": r.hospital_id,
            "hospital_code": hospitals[r.hospital_id].code if r.hospital_id in hospitals else None,
            "hospital_lat": hospitals[r.hospital_id].latitude if r.hospital_id in hospitals else None,
            "hospital_lon": hospitals[r.hospital_id].longitude if r.hospital_id in hospitals else None,
            "distance_km": r.distance_km,
            "estimated_travel_time_min": r.estimated_travel_time_min,
            "base_transport_cost_per_unit": r.base_transport_cost_per_unit,
            "is_available": r.is_available,
            "road_condition": r.road_condition,
            "data_note": r.data_note,
        }
        for r in roads
    ]


@router.get("/vehicles", response_model=list[VehicleResponse])
def list_vehicles(db: Session = Depends(get_db)) -> list[VehicleResponse]:
    """List all fleet vehicles stationed at distribution warehouses."""
    return dispatch_service.list_vehicles(db)


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


@router.get("/road-network/status")
def road_network_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    """Report OpenStreetMap directed road-network cache status and facility connectivity."""
    return road_network_service.get_road_network_status(db)


@router.post("/road-network/sync")
def sync_road_network(
    payload: OSMSyncRequest = OSMSyncRequest(),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Download (if uncached or forced) and cache the Pune & PCMC OSM road network."""
    return road_network_service.sync_osm_road_network(db, force_refresh=payload.force_refresh)


@router.post("/road-network/shortest-path")
def osm_shortest_path_lookup(
    payload: OSMShortestPathRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Compute directed shortest path between two facilities using cached OSM road
    geometry, with automatic graceful fallback to synthetic corridors if offline.
    """
    try:
        return road_network_service.compute_facility_shortest_path(
            db,
            source_code=payload.source_code,
            target_code=payload.target_code,
            weight_metric=payload.weight_metric,
            closed_way_ids=payload.closed_way_ids,
            closed_route_codes=payload.closed_route_codes,
            allow_synthetic_fallback=payload.allow_synthetic_fallback,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/dispatch-plans",
    response_model=DispatchPlanDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_dispatch_plan(
    payload: DispatchPlanCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
) -> DispatchPlanDetailResponse:
    """
    Generate and persist a Google OR-Tools multi-depot vehicle dispatch plan
    from a completed Phase 3 optimization run.
    """
    try:
        result = dispatch_service.generate_dispatch_plan(db, payload)
        audit_service.log_audit_event(
            db,
            actor=admin_user,
            action="dispatch.plan_generated",
            target_entity="dispatch_plan",
            target_id=result.id,
            metadata={"plan_code": result.plan_code, "optimization_run_id": result.optimization_run_id},
        )
        db.commit()
        return result
    except dispatch_service.DispatchDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/vrp", response_model=DispatchPlanDetailResponse, status_code=status.HTTP_201_CREATED)
def run_vrp_alias(
    payload: DispatchPlanCreateRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin),
) -> DispatchPlanDetailResponse:
    """Alias endpoint executing Google OR-Tools CVRP and persisting a DispatchPlan."""
    try:
        result = dispatch_service.generate_dispatch_plan(db, payload)
        audit_service.log_audit_event(
            db,
            actor=admin_user,
            action="dispatch.plan_generated",
            target_entity="dispatch_plan",
            target_id=result.id,
            metadata={"plan_code": result.plan_code, "optimization_run_id": result.optimization_run_id},
        )
        db.commit()
        return result
    except dispatch_service.DispatchDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/dispatch-plans", response_model=list[DispatchPlanSummaryResponse])
def list_dispatch_plans(db: Session = Depends(get_db)) -> list[DispatchPlanSummaryResponse]:
    """List historical dispatch plans ordered most recent first."""
    return dispatch_service.list_dispatch_plans(db)


@router.get("/dispatch-plans/{plan_id}", response_model=DispatchPlanDetailResponse)
def get_dispatch_plan(
    plan_id: int, db: Session = Depends(get_db)
) -> DispatchPlanDetailResponse:
    """Retrieve complete details for a persisted dispatch plan."""
    try:
        return dispatch_service.get_dispatch_plan_detail(db, plan_id)
    except dispatch_service.DispatchDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/dispatch-plans/{plan_id}/status", response_model=DispatchPlanDetailResponse)
def update_dispatch_plan_status(
    plan_id: int,
    payload: DispatchStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> DispatchPlanDetailResponse:
    """Transition a dispatch plan's status following the validated dispatch lifecycle."""
    try:
        return dispatch_service.update_dispatch_plan_status(db, plan_id, payload)
    except dispatch_service.DispatchDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/stops/{stop_id}/status", response_model=DispatchPlanDetailResponse)
def update_delivery_stop_status(
    stop_id: int,
    payload: StopStatusUpdateRequest,
    db: Session = Depends(get_db),
) -> DispatchPlanDetailResponse:
    """Update delivery completion status and delivered quantities at a specific hospital stop."""
    try:
        return dispatch_service.update_delivery_stop_status(db, stop_id, payload)
    except dispatch_service.DispatchDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
