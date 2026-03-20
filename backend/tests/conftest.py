"""Shared test fixtures for AgentBreaker test suite.

Provides an in-memory SQLite database, async session, httpx test client,
and helper functions to create test data (orgs, users, projects, API keys).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_api_key, hash_password
from app.models.agent import Agent
from app.models.api_key import ApiKey
from app.models.incident import Incident
from app.models.organization import Organization
from app.models.project import Project
from app.models.step import Step
from app.models.user import User


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_engine():
    """Create an in-memory SQLite async engine with all tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # Enable foreign keys for SQLite
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Provide an async session bound to the in-memory database."""
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session


# ---------------------------------------------------------------------------
# App / HTTP client fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_app(test_engine):
    """Create a FastAPI app with the test database injected.

    Patches Redis to a no-op mock so tests don't require a Redis server.
    Also patches the DetectionEngine singleton to avoid loading
    sentence-transformers (too slow for CI).
    """
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Patch Redis globally so the app doesn't try to connect
    mock_redis = MagicMock()
    mock_redis.ping = AsyncMock()
    mock_redis.publish = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock()

    with (
        patch("app.main.init_redis", new_callable=AsyncMock, return_value=mock_redis),
        patch("app.main.get_redis_pool", return_value=mock_redis),
        patch("app.core.middleware.RateLimitMiddleware.dispatch", new=_passthrough_dispatch),
    ):
        from app.main import create_app

        app = create_app()
        app.dependency_overrides[get_db] = _override_get_db
        yield app
        app.dependency_overrides.clear()


async def _passthrough_dispatch(self, request, call_next):
    """Bypass rate limiting in tests."""
    return await call_next(request)


@pytest_asyncio.fixture
async def client(test_app):
    """Provide an httpx AsyncClient wired to the test app."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_org(test_session):
    """Create and return a test Organization."""
    org = Organization(
        id=uuid.uuid4(),
        name="Test Org",
        slug="test-org",
        plan="pro",
    )
    test_session.add(org)
    await test_session.flush()
    return org


@pytest_asyncio.fixture
async def test_user(test_session, test_org):
    """Create and return a test User with admin role."""
    user = User(
        id=uuid.uuid4(),
        org_id=test_org.id,
        email="admin@testorg.com",
        hashed_password=hash_password("TestPass123!"),
        role="admin",
    )
    test_session.add(user)
    await test_session.flush()
    return user


@pytest_asyncio.fixture
async def test_project(test_session, test_org):
    """Create and return a test Project."""
    project = Project(
        id=uuid.uuid4(),
        org_id=test_org.id,
        name="Test Project",
        slug="test-project",
        carbon_region="us-east",
    )
    test_session.add(project)
    await test_session.flush()
    return project


@pytest_asyncio.fixture
async def test_api_key_raw(test_session, test_project):
    """Create an API key and return (raw_key, ApiKey object)."""
    raw_key = f"ab_test_{uuid.uuid4().hex}"
    hashed = hash_api_key(raw_key)
    api_key = ApiKey(
        id=uuid.uuid4(),
        project_id=test_project.id,
        key_prefix=raw_key[:16],
        hashed_key=hashed,
        name="Test Key",
        is_active=True,
    )
    test_session.add(api_key)
    await test_session.flush()
    return raw_key, api_key


@pytest_asyncio.fixture
async def auth_token(test_user, test_org):
    """Return a valid JWT token for the test user."""
    return create_access_token(
        user_id=str(test_user.id),
        org_id=str(test_org.id),
    )


@pytest_asyncio.fixture
async def auth_headers(auth_token):
    """Return Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


# ---------------------------------------------------------------------------
# Agent + Step helpers
# ---------------------------------------------------------------------------

async def create_test_agent(
    session: AsyncSession,
    project_id: uuid.UUID,
    external_id: str = "test-agent-001",
    status: str = "running",
    risk_score: float = 0.0,
    total_cost: float = 0.0,
    total_steps: int = 0,
) -> Agent:
    """Insert a test Agent into the database."""
    agent = Agent(
        id=uuid.uuid4(),
        project_id=project_id,
        external_id=external_id,
        name=external_id,
        status=status,
        current_risk_score=risk_score,
        total_cost=total_cost,
        total_tokens=0,
        total_steps=total_steps,
        total_co2_grams=0.0,
        total_kwh=0.0,
    )
    session.add(agent)
    await session.flush()
    return agent


async def create_test_step(
    session: AsyncSession,
    agent_id: uuid.UUID,
    step_number: int,
    input_text: str = "Do something",
    output_text: str = "Done",
    tokens_used: int = 100,
    cost: float = 0.01,
    error_message: str | None = None,
    tool_name: str | None = None,
    context_size: int | None = None,
) -> Step:
    """Insert a test Step into the database."""
    step = Step(
        id=uuid.uuid4(),
        agent_id=agent_id,
        step_number=step_number,
        input_text=input_text,
        output_text=output_text,
        tokens_used=tokens_used,
        cost=cost,
        error_message=error_message,
        tool_name=tool_name,
        context_size=context_size,
    )
    session.add(step)
    await session.flush()
    return step


async def create_test_incident(
    session: AsyncSession,
    agent_id: uuid.UUID,
    project_id: uuid.UUID,
    incident_type: str = "composite",
    risk_score: float = 80.0,
    cost_avoided: float = 5.0,
    co2_avoided: float = 10.0,
    steps_at_kill: int = 15,
    snapshot: dict | None = None,
) -> Incident:
    """Insert a test Incident into the database."""
    incident = Incident(
        id=uuid.uuid4(),
        agent_id=agent_id,
        project_id=project_id,
        incident_type=incident_type,
        risk_score_at_kill=risk_score,
        cost_at_kill=1.5,
        cost_avoided=cost_avoided,
        co2_avoided_grams=co2_avoided,
        kwh_avoided=0.001,
        steps_at_kill=steps_at_kill,
        snapshot=snapshot or {"breakdown": {}, "warnings": []},
        kill_reason_detail="Test kill",
    )
    session.add(incident)
    await session.flush()
    return incident
