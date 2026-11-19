"""Disaster Scenario Simulator API routes (/api/scenarios)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.database.connection import get_db
from app.models.scenario import Scenario
from app.schemas.scenario import (
    ScenarioCreate,
    ScenarioResponse,
    ScenarioRunDetailResponse,
    ScenarioRunSummaryResponse,
    ScenarioSimulationRequest,
)
from app.services import scenario_service

router = APIRouter(
    prefix="/api/scenarios",
    tags=["Scenarios"],
    dependencies=[Depends(require_admin)],
)


@router.get("", response_model=list[ScenarioResponse])
def list_scenarios(db: Session = Depends(get_db)) -> list[ScenarioResponse]:
    """List saved disaster simulation scenarios."""
    return list(db.scalars(select(Scenario).order_by(Scenario.id.desc())).all())


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(payload: ScenarioCreate, db: Session = Depends(get_db)) -> ScenarioResponse:
    """Save a new disaster simulation scenario definition."""
    existing = db.scalar(select(Scenario).where(Scenario.name == payload.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Scenario named '{payload.name}' already exists",
        )
    scenario = Scenario(**payload.model_dump())
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/runs", response_model=list[ScenarioRunSummaryResponse])
def list_scenario_runs(db: Session = Depends(get_db)) -> list[ScenarioRunSummaryResponse]:
    """List historical disaster scenario simulation runs."""
    return scenario_service.list_scenario_runs(db)


@router.get("/runs/{simulation_id}", response_model=ScenarioRunDetailResponse)
def get_scenario_run(
    simulation_id: int, db: Session = Depends(get_db)
) -> ScenarioRunDetailResponse:
    """Retrieve complete details for a persisted scenario simulation run."""
    try:
        return scenario_service.get_scenario_run_detail(db, simulation_id)
    except scenario_service.ScenarioDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/simulate",
    response_model=ScenarioRunDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_ad_hoc_simulation(
    payload: ScenarioSimulationRequest, db: Session = Depends(get_db)
) -> ScenarioRunDetailResponse:
    """Create and execute a reproducible disaster scenario simulation against a baseline run."""
    try:
        return scenario_service.run_disaster_simulation(db, payload)
    except scenario_service.ScenarioDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/{scenario_id}/simulate",
    response_model=ScenarioRunDetailResponse,
    status_code=status.HTTP_201_CREATED,
)
def simulate_saved_scenario(
    scenario_id: int,
    payload: ScenarioSimulationRequest,
    db: Session = Depends(get_db),
) -> ScenarioRunDetailResponse:
    """Execute a simulation for an existing saved scenario definition."""
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")

    # Merge saved scenario parameters with explicit request overrides
    saved_params = scenario.parameters_json or {}
    merged = ScenarioSimulationRequest(
        baseline_run_id=payload.baseline_run_id,
        name=scenario.name,
        description=scenario.description,
        scenario_type=scenario.scenario_type,
        disabled_warehouse_codes=(
            payload.disabled_warehouse_codes
            or saved_params.get("disabled_warehouse_codes", [])
        ),
        closed_route_codes=(
            payload.closed_route_codes or saved_params.get("closed_route_codes", [])
        ),
        closed_way_ids=(
            payload.closed_way_ids or saved_params.get("closed_way_ids", [])
        ),
        demand_spike_hospital_codes=(
            payload.demand_spike_hospital_codes
            or saved_params.get("demand_spike_hospital_codes", [])
        ),
        demand_spike_pct=(
            payload.demand_spike_pct
            if payload.demand_spike_pct > 0
            else float(saved_params.get("demand_spike_pct", 0.0))
        ),
        disabled_vehicle_codes=(
            payload.disabled_vehicle_codes or saved_params.get("disabled_vehicle_codes", [])
        ),
        routing_objective=payload.routing_objective,
        allow_multi_trip=payload.allow_multi_trip,
        max_trips_per_vehicle=payload.max_trips_per_vehicle,
        allow_split_deliveries=payload.allow_split_deliveries,
    )
    try:
        return scenario_service.run_disaster_simulation(db, merged, existing_scenario_id=scenario.id)
    except scenario_service.ScenarioDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a saved scenario."""
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    db.delete(scenario)
    db.commit()
