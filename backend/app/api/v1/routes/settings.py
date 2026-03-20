"""Settings routes -- per-project detection thresholds, budget, and notification config."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.api.v1.deps import get_current_org
from app.models.project import Project

router = APIRouter(prefix="/settings", tags=["settings"])

# --------------------------------------------------------------------------
# Default values
# --------------------------------------------------------------------------

DEFAULT_DETECTION_THRESHOLDS = {
    "kill_threshold": 75,
    "warn_threshold": 50,
    "similarity": 85,
    "diminishing_returns": 0.10,
    "context_inflation_growth": 0.20,
    "context_inflation_novelty": 0.15,
}

DEFAULT_BUDGET = {
    "budget_limit": None,
    "max_cost_per_agent": None,
    "max_steps_per_agent": None,
}

DEFAULT_NOTIFICATIONS = {
    "email_on_kill": True,
    "email_on_warn": False,
    "slack_webhook": None,
    "slack_on_kill": True,
    "slack_on_warn": False,
}


# --------------------------------------------------------------------------
# Request / response schemas
# --------------------------------------------------------------------------

class DetectionThresholds(BaseModel):
    kill_threshold: int = Field(75, ge=1, le=100)
    warn_threshold: int = Field(50, ge=1, le=100)
    similarity: int = Field(85, ge=1, le=100)
    diminishing_returns: float = Field(0.10, ge=0.0, le=1.0)
    context_inflation_growth: float = Field(0.20, ge=0.0, le=5.0)
    context_inflation_novelty: float = Field(0.15, ge=0.0, le=1.0)


class BudgetSettings(BaseModel):
    budget_limit: float | None = None
    max_cost_per_agent: float | None = None
    max_steps_per_agent: int | None = None


class NotificationSettings(BaseModel):
    email_on_kill: bool = True
    email_on_warn: bool = False
    slack_webhook: str | None = None
    slack_on_kill: bool = True
    slack_on_warn: bool = False


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

async def _get_first_project(db: AsyncSession, org_id: UUID) -> Project:
    """Get the first project for the org (settings are per-project)."""
    result = await db.execute(
        select(Project)
        .where(Project.org_id == org_id)
        .order_by(Project.created_at.asc())
        .limit(1)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project", "No projects found for this organization")
    return project


# --------------------------------------------------------------------------
# Detection settings
# --------------------------------------------------------------------------

@router.get("/detection", response_model=DetectionThresholds)
async def get_detection_settings(
    project_id: UUID | None = None,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Return project detection thresholds (or defaults if not set)."""
    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project", str(project_id))
        if project.org_id != org_id:
            raise AuthorizationError("Project does not belong to your organization")
    else:
        project = await _get_first_project(db, org_id)

    thresholds = project.detection_thresholds or {}
    merged = {**DEFAULT_DETECTION_THRESHOLDS, **thresholds}
    return DetectionThresholds(**merged)


@router.put("/detection", response_model=DetectionThresholds)
async def update_detection_settings(
    body: DetectionThresholds,
    project_id: UUID | None = None,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Update detection thresholds with validation."""
    if body.warn_threshold >= body.kill_threshold:
        raise ValidationError("warn_threshold must be less than kill_threshold")

    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project", str(project_id))
        if project.org_id != org_id:
            raise AuthorizationError("Project does not belong to your organization")
    else:
        project = await _get_first_project(db, org_id)

    project.detection_thresholds = body.model_dump()
    await db.flush()
    return body


# --------------------------------------------------------------------------
# Budget settings
# --------------------------------------------------------------------------

@router.get("/budget", response_model=BudgetSettings)
async def get_budget_settings(
    project_id: UUID | None = None,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Return project budget limits."""
    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project", str(project_id))
        if project.org_id != org_id:
            raise AuthorizationError("Project does not belong to your organization")
    else:
        project = await _get_first_project(db, org_id)

    return BudgetSettings(
        budget_limit=project.budget_limit,
        max_cost_per_agent=project.max_cost_per_agent,
        max_steps_per_agent=project.max_steps_per_agent,
    )


@router.put("/budget", response_model=BudgetSettings)
async def update_budget_settings(
    body: BudgetSettings,
    project_id: UUID | None = None,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Update budget limits."""
    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project", str(project_id))
        if project.org_id != org_id:
            raise AuthorizationError("Project does not belong to your organization")
    else:
        project = await _get_first_project(db, org_id)

    project.budget_limit = body.budget_limit
    project.max_cost_per_agent = body.max_cost_per_agent
    project.max_steps_per_agent = body.max_steps_per_agent
    await db.flush()
    return body


# --------------------------------------------------------------------------
# Notification settings
# --------------------------------------------------------------------------

@router.get("/notifications", response_model=NotificationSettings)
async def get_notification_settings(
    project_id: UUID | None = None,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Return notification configuration."""
    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project", str(project_id))
        if project.org_id != org_id:
            raise AuthorizationError("Project does not belong to your organization")
    else:
        project = await _get_first_project(db, org_id)

    # Notification settings stored in detection_thresholds JSONB under "notifications" key
    thresholds = project.detection_thresholds or {}
    notif = thresholds.get("notifications", {})
    merged = {**DEFAULT_NOTIFICATIONS, **notif}
    return NotificationSettings(**merged)


@router.put("/notifications", response_model=NotificationSettings)
async def update_notification_settings(
    body: NotificationSettings,
    project_id: UUID | None = None,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Update notification configuration."""
    if project_id:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project is None:
            raise NotFoundError("Project", str(project_id))
        if project.org_id != org_id:
            raise AuthorizationError("Project does not belong to your organization")
    else:
        project = await _get_first_project(db, org_id)

    thresholds = project.detection_thresholds or {}
    thresholds["notifications"] = body.model_dump()
    project.detection_thresholds = thresholds
    await db.flush()
    return body
