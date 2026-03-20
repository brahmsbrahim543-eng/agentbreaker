"""Auth routes -- registration, login, and current user info."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_user
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.services.auth import register_user, authenticate_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new organization and admin user, return JWT."""
    result = await register_user(
        db=db,
        org_name=body.org_name,
        email=body.email,
        password=body.password,
    )
    return TokenResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email/password, return JWT."""
    result = await authenticate_user(
        db=db,
        email=body.email,
        password=body.password,
    )
    return TokenResponse(
        access_token=result["access_token"],
        token_type=result["token_type"],
    )


@router.get("/me")
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return current user profile with organization info."""
    # Eagerly load organization
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select
    from app.models.user import User as UserModel

    result = await db.execute(
        select(UserModel)
        .options(selectinload(UserModel.organization))
        .where(UserModel.id == user.id)
    )
    full_user = result.scalar_one()

    return {
        "id": str(full_user.id),
        "email": full_user.email,
        "role": full_user.role,
        "created_at": full_user.created_at.isoformat(),
        "organization": {
            "id": str(full_user.organization.id),
            "name": full_user.organization.name,
            "slug": full_user.organization.slug,
            "plan": full_user.organization.plan,
            "created_at": full_user.organization.created_at.isoformat(),
        },
    }
