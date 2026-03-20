"""Incident routes -- list, detail, export, and stats for detected incidents."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, AuthorizationError
from app.api.v1.deps import get_current_org
from app.models.incident import Incident
from app.models.agent import Agent
from app.models.project import Project
from app.schemas.incident import (
    IncidentResponse,
    IncidentDetail,
    IncidentListResponse,
    IncidentStats,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=IncidentListResponse)
async def list_incidents(
    incident_type: str | None = Query(None),
    agent_id: UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """List incidents across all projects in the org with optional filters."""
    project_ids_q = select(Project.id).where(Project.org_id == org_id)

    base = select(Incident).where(Incident.project_id.in_(project_ids_q))
    count_q = select(func.count(Incident.id)).where(Incident.project_id.in_(project_ids_q))

    if incident_type:
        base = base.where(Incident.incident_type == incident_type)
        count_q = count_q.where(Incident.incident_type == incident_type)
    if agent_id:
        base = base.where(Incident.agent_id == agent_id)
        count_q = count_q.where(Incident.agent_id == agent_id)
    if date_from:
        base = base.where(Incident.created_at >= date_from)
        count_q = count_q.where(Incident.created_at >= date_from)
    if date_to:
        base = base.where(Incident.created_at <= date_to)
        count_q = count_q.where(Incident.created_at <= date_to)

    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    offset = (page - 1) * per_page
    base = base.order_by(Incident.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(base)
    incidents = result.scalars().all()

    # We need agent names for the response
    agent_ids = list({i.agent_id for i in incidents})
    agent_map: dict[UUID, str] = {}
    if agent_ids:
        agents_result = await db.execute(
            select(Agent.id, Agent.name).where(Agent.id.in_(agent_ids))
        )
        for row in agents_result:
            agent_map[row[0]] = row[1]

    items = [
        IncidentResponse(
            id=i.id,
            agent_id=i.agent_id,
            agent_name=agent_map.get(i.agent_id, "Unknown"),
            incident_type=i.incident_type,
            risk_score_at_kill=i.risk_score_at_kill,
            cost_avoided=i.cost_avoided,
            co2_avoided_grams=i.co2_avoided_grams,
            steps_at_kill=i.steps_at_kill,
            created_at=i.created_at,
        )
        for i in incidents
    ]

    return IncidentListResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/stats", response_model=IncidentStats)
async def incident_stats(
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Aggregated incident statistics by type."""
    project_ids_q = select(Project.id).where(Project.org_id == org_id)

    # Total count
    total_result = await db.execute(
        select(func.count(Incident.id)).where(Incident.project_id.in_(project_ids_q))
    )
    total_count = total_result.scalar() or 0

    # By type
    type_result = await db.execute(
        select(Incident.incident_type, func.count(Incident.id))
        .where(Incident.project_id.in_(project_ids_q))
        .group_by(Incident.incident_type)
    )
    by_type = {row[0]: row[1] for row in type_result}

    # Total cost avoided
    cost_result = await db.execute(
        select(func.coalesce(func.sum(Incident.cost_avoided), 0.0))
        .where(Incident.project_id.in_(project_ids_q))
    )
    total_cost_avoided = cost_result.scalar() or 0.0

    # Total CO2 avoided
    co2_result = await db.execute(
        select(func.coalesce(func.sum(Incident.co2_avoided_grams), 0.0))
        .where(Incident.project_id.in_(project_ids_q))
    )
    total_co2_avoided = co2_result.scalar() or 0.0

    return IncidentStats(
        total_count=total_count,
        by_type=by_type,
        total_cost_avoided=total_cost_avoided,
        total_co2_avoided_grams=total_co2_avoided,
    )


@router.get("/{incident_id}", response_model=IncidentDetail)
async def get_incident(
    incident_id: UUID,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Get full incident detail with snapshot."""
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise NotFoundError("Incident", str(incident_id))

    # Verify org ownership
    proj_result = await db.execute(
        select(Project).where(Project.id == incident.project_id)
    )
    project = proj_result.scalar_one_or_none()
    if project is None or project.org_id != org_id:
        raise AuthorizationError("Incident does not belong to your organization")

    # Get agent name
    agent_result = await db.execute(
        select(Agent.name).where(Agent.id == incident.agent_id)
    )
    agent_name = agent_result.scalar() or "Unknown"

    return IncidentDetail(
        id=incident.id,
        agent_id=incident.agent_id,
        agent_name=agent_name,
        incident_type=incident.incident_type,
        risk_score_at_kill=incident.risk_score_at_kill,
        cost_avoided=incident.cost_avoided,
        co2_avoided_grams=incident.co2_avoided_grams,
        steps_at_kill=incident.steps_at_kill,
        created_at=incident.created_at,
        snapshot=incident.snapshot or {},
        kill_reason_detail=incident.kill_reason_detail or "",
    )


@router.get("/{incident_id}/export")
async def export_incident(
    incident_id: UUID,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Export incident as a downloadable JSON file."""
    result = await db.execute(
        select(Incident).where(Incident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if incident is None:
        raise NotFoundError("Incident", str(incident_id))

    proj_result = await db.execute(
        select(Project).where(Project.id == incident.project_id)
    )
    project = proj_result.scalar_one_or_none()
    if project is None or project.org_id != org_id:
        raise AuthorizationError("Incident does not belong to your organization")

    agent_result = await db.execute(
        select(Agent.name).where(Agent.id == incident.agent_id)
    )
    agent_name = agent_result.scalar() or "Unknown"

    export_data = {
        "incident_id": str(incident.id),
        "agent_id": str(incident.agent_id),
        "agent_name": agent_name,
        "project_id": str(incident.project_id),
        "incident_type": incident.incident_type,
        "risk_score_at_kill": incident.risk_score_at_kill,
        "cost_at_kill": incident.cost_at_kill,
        "cost_avoided": incident.cost_avoided,
        "co2_avoided_grams": incident.co2_avoided_grams,
        "kwh_avoided": incident.kwh_avoided,
        "steps_at_kill": incident.steps_at_kill,
        "snapshot": incident.snapshot,
        "kill_reason_detail": incident.kill_reason_detail,
        "created_at": incident.created_at.isoformat(),
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="incident_{incident_id}.json"',
        },
    )
