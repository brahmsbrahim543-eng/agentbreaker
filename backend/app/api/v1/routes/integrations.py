"""Integration management routes -- list, configure, and check health of provider integrations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_org
from app.integrations import AVAILABLE_INTEGRATIONS

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class IntegrationInfo(BaseModel):
    """Public description of an available integration."""

    provider: str
    name: str
    description: str
    classes: list[str]
    is_configured: bool = False
    status: str = "not_configured"  # not_configured | healthy | unhealthy


class IntegrationListResponse(BaseModel):
    items: list[IntegrationInfo]
    total: int


class IntegrationConfigureRequest(BaseModel):
    """Payload to configure a provider integration for a project."""

    agentbreaker_url: str = Field(
        ...,
        description="Public URL of this AgentBreaker deployment.",
        examples=["https://agentbreaker-xyz.run.app"],
    )
    risk_threshold: float = Field(
        80.0, ge=0, le=100,
        description="Risk score above which agents are killed.",
    )
    cost_limit: float = Field(
        25.0, ge=0,
        description="Maximum cumulative cost (USD) per agent session.",
    )
    cost_per_1k_tokens: float = Field(
        0.03, ge=0,
        description="Fallback cost rate per 1k tokens.",
    )
    kill_on_error: bool = Field(
        False,
        description="If true, treat AgentBreaker API errors as kill signals (fail-closed).",
    )
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Provider-specific configuration.",
    )


class IntegrationConfigureResponse(BaseModel):
    provider: str
    status: str
    message: str
    snippet: str = Field(
        "",
        description="Code snippet showing how to use the integration.",
    )


class IntegrationStatusResponse(BaseModel):
    provider: str
    status: str
    latency_ms: float | None = None
    message: str
    checked_at: str


# ---------------------------------------------------------------------------
# In-memory configuration store (per-org, per-provider)
# In production this would be in the DB; for the MVP it lives in memory.
# ---------------------------------------------------------------------------

_configs: dict[str, dict[str, dict[str, Any]]] = {}


def _get_config(org_id: str, provider: str) -> dict[str, Any] | None:
    return _configs.get(org_id, {}).get(provider)


def _set_config(org_id: str, provider: str, config: dict[str, Any]) -> None:
    _configs.setdefault(org_id, {})[provider] = config


# ---------------------------------------------------------------------------
# Code snippets per provider
# ---------------------------------------------------------------------------

_SNIPPETS: dict[str, str] = {
    "azure": """\
from agentbreaker.integrations.azure import AzureAgentBreakerMiddleware

middleware = AzureAgentBreakerMiddleware(
    agentbreaker_url="{url}",
    api_key="<YOUR_API_KEY>",
    risk_threshold={risk_threshold},
    cost_per_1k_tokens={cost_per_1k_tokens},
    kill_on_error={kill_on_error},
)

protected_agent = middleware.protect(your_agent)
""",
    "gcp": """\
from agentbreaker.integrations.gcp import VertexAgentBreakerCallback

callback = VertexAgentBreakerCallback(
    agentbreaker_url="{url}",
    api_key="<YOUR_API_KEY>",
    risk_threshold={risk_threshold},
    cost_per_1k_tokens={cost_per_1k_tokens},
    kill_on_error={kill_on_error},
)

agent.run(callbacks=[callback])
""",
    "salesforce": """\
from agentbreaker.integrations.salesforce import AgentforceMonitor

monitor = AgentforceMonitor(
    agentbreaker_url="{url}",
    api_key="<YOUR_API_KEY>",
    risk_threshold={risk_threshold},
    session_cost_limit={cost_limit},
    cost_per_1k_tokens={cost_per_1k_tokens},
    kill_on_error={kill_on_error},
)
""",
    "openai": """\
from agentbreaker.integrations.openai import OpenAIAgentGuard

guard = OpenAIAgentGuard(
    agentbreaker_url="{url}",
    api_key="<YOUR_API_KEY>",
    risk_threshold={risk_threshold},
    cost_limit={cost_limit},
    cost_per_1k_tokens={cost_per_1k_tokens},
    kill_on_error={kill_on_error},
)

result = await guard.run(agent, input="...")
""",
    "langchain": """\
from agentbreaker.integrations.langchain import LangChainAgentMonitor

monitor = LangChainAgentMonitor(
    agentbreaker_url="{url}",
    api_key="<YOUR_API_KEY>",
    risk_threshold={risk_threshold},
    cost_limit={cost_limit},
    cost_per_1k_tokens={cost_per_1k_tokens},
    kill_on_error={kill_on_error},
)

# As callback
agent.run("...", callbacks=[monitor.as_callback()])

# Or as wrapper
protected = monitor.wrap_agent(agent_executor)
""",
}


def _render_snippet(provider: str, config: dict[str, Any]) -> str:
    template = _SNIPPETS.get(provider, "# No snippet available for this provider.")
    try:
        return template.format(
            url=config.get("agentbreaker_url", "https://your-agentbreaker.run.app"),
            risk_threshold=config.get("risk_threshold", 80.0),
            cost_limit=config.get("cost_limit", 25.0),
            cost_per_1k_tokens=config.get("cost_per_1k_tokens", 0.03),
            kill_on_error=config.get("kill_on_error", False),
        )
    except (KeyError, IndexError):
        return template


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=IntegrationListResponse)
async def list_integrations(
    org_id: UUID = Depends(get_current_org),
) -> IntegrationListResponse:
    """List all available integrations and their configuration status.

    Returns every supported provider with metadata and whether it has been
    configured for the current organisation.
    """
    org_key = str(org_id)
    items: list[IntegrationInfo] = []

    for provider, meta in AVAILABLE_INTEGRATIONS.items():
        config = _get_config(org_key, provider)
        items.append(
            IntegrationInfo(
                provider=provider,
                name=meta["name"],
                description=meta["description"],
                classes=meta["classes"],
                is_configured=config is not None,
                status="configured" if config else "not_configured",
            )
        )

    return IntegrationListResponse(items=items, total=len(items))


@router.post(
    "/{provider}/configure",
    response_model=IntegrationConfigureResponse,
)
async def configure_integration(
    provider: str,
    body: IntegrationConfigureRequest,
    org_id: UUID = Depends(get_current_org),
) -> IntegrationConfigureResponse:
    """Configure an integration for the current organisation.

    Stores the configuration and returns a code snippet showing how to
    use the integration in the target platform.
    """
    if provider not in AVAILABLE_INTEGRATIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider}'. "
            f"Available: {', '.join(AVAILABLE_INTEGRATIONS)}",
        )

    config = body.model_dump()
    _set_config(str(org_id), provider, config)

    snippet = _render_snippet(provider, config)

    return IntegrationConfigureResponse(
        provider=provider,
        status="configured",
        message=f"{AVAILABLE_INTEGRATIONS[provider]['name']} integration configured successfully.",
        snippet=snippet,
    )


@router.get(
    "/{provider}/status",
    response_model=IntegrationStatusResponse,
)
async def get_integration_status(
    provider: str,
    org_id: UUID = Depends(get_current_org),
) -> IntegrationStatusResponse:
    """Check the health of an integration.

    Verifies that the integration is configured and that the AgentBreaker
    endpoint is reachable.
    """
    if provider not in AVAILABLE_INTEGRATIONS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown provider '{provider}'.",
        )

    config = _get_config(str(org_id), provider)
    now = datetime.now(timezone.utc).isoformat()

    if config is None:
        return IntegrationStatusResponse(
            provider=provider,
            status="not_configured",
            message="Integration has not been configured yet.",
            checked_at=now,
        )

    # Health check: ping the configured AgentBreaker URL
    import httpx

    url = config.get("agentbreaker_url", "").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            start = datetime.now(timezone.utc)
            resp = await client.get(f"{url}/health")
            latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            if resp.status_code < 400:
                return IntegrationStatusResponse(
                    provider=provider,
                    status="healthy",
                    latency_ms=round(latency, 1),
                    message=f"{AVAILABLE_INTEGRATIONS[provider]['name']} integration is healthy.",
                    checked_at=now,
                )
            else:
                return IntegrationStatusResponse(
                    provider=provider,
                    status="unhealthy",
                    latency_ms=round(latency, 1),
                    message=f"Health check returned HTTP {resp.status_code}.",
                    checked_at=now,
                )
    except httpx.HTTPError as exc:
        return IntegrationStatusResponse(
            provider=provider,
            status="unhealthy",
            message=f"Cannot reach AgentBreaker at {url}: {exc}",
            checked_at=now,
        )
