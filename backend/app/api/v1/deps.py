"""Shared FastAPI dependencies for authentication and authorization."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import AuthenticationError
from app.core.security import verify_token, hash_api_key
from app.models.user import User
from app.models.api_key import ApiKey


async def get_current_user(
    authorization: str = Header(..., description="Bearer <JWT>"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract Bearer token from Authorization header, verify JWT, return User."""
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Authorization header must start with 'Bearer '")

    token = authorization[7:]
    try:
        payload = verify_token(token)
    except ValueError:
        raise AuthenticationError("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Token missing subject claim")

    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError("User not found")

    return user


async def get_current_org(
    user: User = Depends(get_current_user),
) -> UUID:
    """Return the org_id of the currently authenticated user."""
    return user.org_id


async def verify_api_key_dep(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """Hash the provided API key, look it up in the ApiKey table, update last_used_at,
    and return the associated project_id."""
    hashed = hash_api_key(x_api_key)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.hashed_key == hashed,
            ApiKey.is_active == True,  # noqa: E712
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise AuthenticationError("Invalid or revoked API key")

    api_key.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    return api_key.project_id
