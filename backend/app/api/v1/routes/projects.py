"""Project routes -- CRUD for projects scoped to the current organization."""

import re
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, AuthorizationError
from app.api.v1.deps import get_current_user, get_current_org
from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """List all projects belonging to the current organization."""
    result = await db.execute(
        select(Project)
        .where(Project.org_id == org_id)
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [_project_to_response(p) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    body: ProjectCreate,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Create a new project in the current organization."""
    project = Project(
        org_id=org_id,
        name=body.name,
        slug=_slugify(body.name),
        budget_limit=body.budget_limit,
        max_cost_per_agent=body.max_cost_per_agent,
        max_steps_per_agent=body.max_steps_per_agent,
        detection_thresholds=body.detection_thresholds,
        carbon_region=body.carbon_region,
    )
    db.add(project)
    await db.flush()
    return _project_to_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Get details of a specific project."""
    project = await _get_project_or_404(db, project_id, org_id)
    return _project_to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing project's settings."""
    project = await _get_project_or_404(db, project_id, org_id)

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "name" and value is not None:
            project.slug = _slugify(value)
        setattr(project, field, value)

    await db.flush()
    return _project_to_response(project)


async def _get_project_or_404(
    db: AsyncSession, project_id: UUID, org_id: UUID
) -> Project:
    """Fetch a project ensuring it belongs to the given org, or raise 404."""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project", str(project_id))
    if project.org_id != org_id:
        raise AuthorizationError("Project does not belong to your organization")
    return project


def _project_to_response(project: Project) -> ProjectResponse:
    """Convert a Project ORM object to the response schema."""
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        slug=project.slug,
        budget_limit=project.budget_limit,
        max_cost_per_agent=project.max_cost_per_agent,
        max_steps_per_agent=project.max_steps_per_agent,
        detection_thresholds=project.detection_thresholds,
        carbon_region=project.carbon_region,
        created_at=project.created_at,
        updated_at=project.created_at,  # Project model has no updated_at; use created_at
    )
