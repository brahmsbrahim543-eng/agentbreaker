"""Agent routes -- list and detail views for monitored agents."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, AuthorizationError
from app.api.v1.deps import get_current_org
from app.models.agent import Agent
from app.models.step import Step
from app.models.project import Project
from app.schemas.agent import AgentResponse, AgentDetail, AgentListResponse
from app.schemas.step import StepResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=AgentListResponse)
async def list_agents(
    status: str | None = Query(None, description="Filter by agent status"),
    risk_min: float | None = Query(None, ge=0, le=100),
    risk_max: float | None = Query(None, ge=0, le=100),
    sort_by: str = Query("last_seen_at", regex="^(last_seen_at|current_risk_score|total_cost|total_steps)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """List agents across all projects in the org, with filters and pagination."""
    # Get project IDs belonging to this org
    project_ids_q = select(Project.id).where(Project.org_id == org_id)

    # Base query
    base = select(Agent).where(Agent.project_id.in_(project_ids_q))
    count_q = select(func.count(Agent.id)).where(Agent.project_id.in_(project_ids_q))

    # Apply filters
    if status:
        base = base.where(Agent.status == status)
        count_q = count_q.where(Agent.status == status)
    if risk_min is not None:
        base = base.where(Agent.current_risk_score >= risk_min)
        count_q = count_q.where(Agent.current_risk_score >= risk_min)
    if risk_max is not None:
        base = base.where(Agent.current_risk_score <= risk_max)
        count_q = count_q.where(Agent.current_risk_score <= risk_max)

    # Sort
    sort_column = getattr(Agent, sort_by)
    if sort_order == "desc":
        base = base.order_by(sort_column.desc())
    else:
        base = base.order_by(sort_column.asc())

    # Count
    total_result = await db.execute(count_q)
    total = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    base = base.offset(offset).limit(per_page)

    result = await db.execute(base)
    agents = result.scalars().all()

    return AgentListResponse(
        items=[AgentResponse.model_validate(a) for a in agents],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{agent_id}", response_model=AgentDetail)
async def get_agent(
    agent_id: UUID,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Get agent detail including the last 20 steps."""
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise NotFoundError("Agent", str(agent_id))

    # Verify ownership via project -> org
    proj_result = await db.execute(
        select(Project).where(Project.id == agent.project_id)
    )
    project = proj_result.scalar_one_or_none()
    if project is None or project.org_id != org_id:
        raise AuthorizationError("Agent does not belong to your organization")

    # Fetch last 20 steps
    steps_result = await db.execute(
        select(Step)
        .where(Step.agent_id == agent.id)
        .order_by(Step.step_number.desc())
        .limit(20)
    )
    steps = steps_result.scalars().all()

    recent_steps = [
        {
            "step_number": s.step_number,
            "input_preview": s.input_text[:200] if s.input_text else "",
            "output_preview": s.output_text[:200] if s.output_text else "",
            "tokens_used": s.tokens_used,
            "cost": s.cost,
            "tool_name": s.tool_name,
            "error_message": s.error_message,
            "created_at": s.created_at.isoformat(),
        }
        for s in reversed(steps)  # chronological order
    ]

    return AgentDetail(
        id=agent.id,
        external_id=agent.external_id,
        name=agent.name,
        status=agent.status,
        current_risk_score=agent.current_risk_score,
        total_cost=agent.total_cost,
        total_tokens=agent.total_tokens,
        total_steps=agent.total_steps,
        total_co2_grams=agent.total_co2_grams,
        total_kwh=agent.total_kwh,
        last_seen_at=agent.last_seen_at,
        recent_steps=recent_steps,
    )
