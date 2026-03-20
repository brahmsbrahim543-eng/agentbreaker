"""API Key routes -- generate, list, and revoke API keys for a project."""

import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError, AuthorizationError
from app.core.security import hash_api_key
from app.api.v1.deps import get_current_org
from app.models.api_key import ApiKey
from app.models.project import Project

router = APIRouter(prefix="/projects/{project_id}/api-keys", tags=["api-keys"])


# --------------------------------------------------------------------------
# Request / response schemas (local to this module)
# --------------------------------------------------------------------------

class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    key: str  # plain-text key, shown only once
    key_prefix: str
    created_at: datetime


class ApiKeyListItem(BaseModel):
    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------

@router.post("", response_model=ApiKeyCreateResponse, status_code=201)
async def create_api_key(
    project_id: UUID,
    body: ApiKeyCreateRequest,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key for a project. The plain key is returned only once."""
    await _verify_project_ownership(db, project_id, org_id)

    # Generate key: ab_live_ + 32 hex chars (16 random bytes)
    raw_key = "ab_live_" + secrets.token_hex(16)
    prefix = raw_key[:16]  # "ab_live_" + first 8 hex chars
    hashed = hash_api_key(raw_key)

    api_key = ApiKey(
        project_id=project_id,
        key_prefix=prefix,
        hashed_key=hashed,
        name=body.name,
        is_active=True,
    )
    db.add(api_key)
    await db.flush()

    return ApiKeyCreateResponse(
        id=str(api_key.id),
        name=api_key.name,
        key=raw_key,
        key_prefix=prefix,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyListItem])
async def list_api_keys(
    project_id: UUID,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys for a project (prefix only, no plain key)."""
    await _verify_project_ownership(db, project_id, org_id)

    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.project_id == project_id)
        .order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()

    return [
        ApiKeyListItem(
            id=str(k.id),
            name=k.name,
            key_prefix=k.key_prefix,
            is_active=k.is_active,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    project_id: UUID,
    key_id: UUID,
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key by setting is_active=False."""
    await _verify_project_ownership(db, project_id, org_id)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.project_id == project_id,
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise NotFoundError("API Key", str(key_id))

    api_key.is_active = False
    await db.flush()


async def _verify_project_ownership(
    db: AsyncSession, project_id: UUID, org_id: UUID
) -> Project:
    """Ensure the project exists and belongs to the caller's org."""
    result = await db.execute(
        select(Project).where(Project.id == project_id)
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise NotFoundError("Project", str(project_id))
    if project.org_id != org_id:
        raise AuthorizationError("Project does not belong to your organization")
    return project
