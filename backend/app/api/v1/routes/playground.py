"""Playground routes -- interactive demo scenarios with real detection engine."""

import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.deps import get_current_user
from app.core.redis import get_redis_pool
from app.services.playground import get_scenario_list, run_simulation

router = APIRouter(prefix="/playground", tags=["playground"])


class SimulateRequest(BaseModel):
    scenario: str = Field(..., description="Scenario ID: semantic_loop, cost_explosion, or error_cascade")


class SimulateResponse(BaseModel):
    session_id: str
    scenario: str
    message: str


@router.get("/scenarios")
async def list_scenarios(
    _user=Depends(get_current_user),
):
    """Return available simulation scenarios."""
    return get_scenario_list()


@router.post("/simulate", response_model=SimulateResponse)
async def start_simulation(
    body: SimulateRequest,
    _user=Depends(get_current_user),
):
    """Start a simulation scenario. Results are streamed via WebSocket at
    /ws/playground/{session_id}.
    """
    session_id = uuid4().hex[:12]

    # Get Redis for pub/sub
    redis = get_redis_pool()

    # Launch simulation as a background task
    asyncio.create_task(
        run_simulation(
            scenario_id=body.scenario,
            session_id=session_id,
            redis=redis,
        )
    )

    return SimulateResponse(
        session_id=session_id,
        scenario=body.scenario,
        message=f"Simulation started. Connect to /ws/playground/{session_id} for live results.",
    )
