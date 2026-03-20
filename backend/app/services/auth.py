"""Authentication service -- registration and login logic."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ValidationError
from app.core.security import hash_password, verify_password, create_access_token
from app.models.organization import Organization
from app.models.user import User


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


async def register_user(
    db: AsyncSession,
    org_name: str,
    email: str,
    password: str,
) -> dict:
    """Create a new organization and admin user, return JWT token data."""
    # Check for duplicate email
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise ValidationError("Email already registered")

    # Create organization
    slug = _slugify(org_name)
    # Ensure slug uniqueness by appending a suffix if needed
    slug_check = await db.execute(
        select(Organization).where(Organization.slug == slug)
    )
    if slug_check.scalar_one_or_none() is not None:
        import uuid as _uuid
        slug = f"{slug}-{_uuid.uuid4().hex[:6]}"

    org = Organization(name=org_name, slug=slug)
    db.add(org)
    await db.flush()

    # Create admin user
    user = User(
        org_id=org.id,
        email=email,
        hashed_password=hash_password(password),
        role="admin",
    )
    db.add(user)
    await db.flush()

    token = create_access_token(user_id=str(user.id), org_id=str(org.id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "org_id": str(org.id),
    }


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> dict:
    """Verify email/password and return JWT token data."""
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise AuthenticationError("Invalid email or password")

    if not verify_password(password, user.hashed_password):
        raise AuthenticationError("Invalid email or password")

    token = create_access_token(user_id=str(user.id), org_id=str(user.org_id))
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": str(user.id),
        "org_id": str(user.org_id),
    }
