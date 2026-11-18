"""Disaster Scenario Simulator API routes (/api/scenarios)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.models.scenario import Scenario

router = APIRouter(prefix="/api/scenarios", tags=["Scenarios"])


class ScenarioCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=120)
    description: str | None = None
    scenario_type: Literal[
        "warehouse_failure", "road_closure", "demand_surge", "combined", "custom"
    ] = "custom"
    parameters_json: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


class ScenarioResponse(ScenarioCreate):
    id: int

    model_config = ConfigDict(from_attributes=True)


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


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)) -> None:
    """Delete a saved scenario."""
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    db.delete(scenario)
    db.commit()


@router.post("/{scenario_id}/simulate")
def simulate_scenario_stub(scenario_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Placeholder endpoint for automated baseline-vs-disrupted comparison.

    TODO: Execute baseline and disrupted runs via app.simulation.scenario_engine
    and return delta KPIs (cost increase, unmet critical demand shift).
    """
    scenario = db.get(Scenario, scenario_id)
    if not scenario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scenario not found")
    return {
        "scenario_id": scenario.id,
        "scenario_name": scenario.name,
        "status": "TODO_IMPLEMENTATION",
        "message": (
            "Scenario engine perturbation helper is initialized; full baseline-vs-disrupted "
            "comparison workflow will be connected in the Disaster Simulator sprint."
        ),
    }
