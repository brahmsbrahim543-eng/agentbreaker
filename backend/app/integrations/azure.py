"""Azure AI Foundry Integration -- AgentBreaker as an Azure AI service.

Provides middleware and callbacks that integrate directly with:
- Azure AI Agent Service (preview)
- Azure OpenAI Service
- Semantic Kernel agents
- AutoGen agents running on Azure

Usage with Azure AI Agent Service::

    from agentbreaker.integrations.azure import AzureAgentBreakerMiddleware

    middleware = AzureAgentBreakerMiddleware(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    # Wraps any Azure AI agent
    protected_agent = middleware.protect(agent)

Usage with Semantic Kernel::

    from agentbreaker.integrations.azure import SemanticKernelPlugin

    plugin = SemanticKernelPlugin(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )
    kernel.add_plugin(plugin, "agentbreaker")

Usage with AutoGen::

    from agentbreaker.integrations.azure import AutoGenMonitor

    monitor = AutoGenMonitor(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )
    monitor.attach(group_chat_manager)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

import httpx

logger = logging.getLogger("agentbreaker.integrations.azure")

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

@dataclass
class AgentBreakerVerdict:
    """Result returned by the AgentBreaker analysis API."""

    step_number: int
    risk_score: float
    action: str  # "allow" | "warn" | "kill"
    warnings: list[str]
    risk_breakdown: dict[str, float]
    carbon_impact: dict[str, Any] | None = None


class _BaseIntegration:
    """Shared HTTP transport for all Azure integration classes."""

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        self._url = agentbreaker_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._kill_on_error = kill_on_error
        self._client: httpx.AsyncClient | None = None

    # -- lifecycle -----------------------------------------------------------

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._url,
                headers={
                    "X-API-Key": self._api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "agentbreaker-azure/1.0",
                },
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        """Cleanly shut down the underlying HTTP connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -- core analysis call --------------------------------------------------

    async def _analyze_step(
        self,
        agent_id: str,
        step_input: str,
        step_output: str,
        tokens: int,
        cost: float,
        *,
        tool: str | None = None,
        duration_ms: int | None = None,
        context_size: int | None = None,
    ) -> AgentBreakerVerdict:
        """Send a step to the AgentBreaker ``/ingest/step`` endpoint.

        Returns an :class:`AgentBreakerVerdict` with the risk analysis.
        On network or server errors the behaviour depends on
        ``kill_on_error``: if *True*, a synthetic *kill* verdict is returned
        (fail-closed); otherwise a synthetic *allow* is returned (fail-open).
        """
        client = await self._ensure_client()

        payload = {
            "agent_id": agent_id,
            "input": step_input,
            "output": step_output,
            "tokens": tokens,
            "cost": cost,
        }
        if tool is not None:
            payload["tool"] = tool
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if context_size is not None:
            payload["context_size"] = context_size

        try:
            resp = await client.post("/api/v1/ingest/step", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return AgentBreakerVerdict(
                step_number=data["step_number"],
                risk_score=data["risk_score"],
                action=data["action"],
                warnings=data.get("warnings", []),
                risk_breakdown=data.get("risk_breakdown", {}),
                carbon_impact=data.get("carbon_impact"),
            )
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.error("AgentBreaker analysis failed: %s", exc)
            if self._kill_on_error:
                return AgentBreakerVerdict(
                    step_number=-1,
                    risk_score=100.0,
                    action="kill",
                    warnings=[f"AgentBreaker unreachable: {exc}"],
                    risk_breakdown={},
                )
            return AgentBreakerVerdict(
                step_number=-1,
                risk_score=0.0,
                action="allow",
                warnings=[f"AgentBreaker unreachable (fail-open): {exc}"],
                risk_breakdown={},
            )


# ---------------------------------------------------------------------------
# Protocol for "anything that looks like an Azure AI agent"
# ---------------------------------------------------------------------------

@runtime_checkable
class AzureAgent(Protocol):
    """Minimal protocol describing an Azure AI Agent Service agent."""

    async def run(self, *, input: str, **kwargs: Any) -> Any: ...


# ---------------------------------------------------------------------------
# AzureAgentBreakerMiddleware
# ---------------------------------------------------------------------------

class AzureAgentBreakerMiddleware(_BaseIntegration):
    """Middleware that wraps Azure AI agents with AgentBreaker protection.

    After each agent step, the middleware sends telemetry to the AgentBreaker
    analysis API.  If the API returns a **kill** verdict, the agent run is
    halted and a :class:`AgentKilledException` is raised.

    Parameters
    ----------
    agentbreaker_url:
        Base URL of your AgentBreaker deployment (e.g.
        ``https://agentbreaker-xyz.run.app``).
    api_key:
        A project-scoped AgentBreaker API key (``ab_live_...``).
    cost_per_1k_tokens:
        Fallback cost rate when the agent framework does not report cost.
    risk_threshold:
        Risk score (0--100) above which the middleware will kill the agent.
        Defaults to 80.
    kill_on_error:
        If *True*, treat AgentBreaker API failures as kill signals
        (fail-closed).  Default is *False* (fail-open).
    on_kill:
        Optional async callback invoked when an agent is killed.  Receives
        the :class:`AgentBreakerVerdict`.
    """

    class AgentKilledException(Exception):
        """Raised when AgentBreaker terminates an agent run."""

        def __init__(self, verdict: AgentBreakerVerdict) -> None:
            self.verdict = verdict
            super().__init__(
                f"AgentBreaker killed agent -- risk_score={verdict.risk_score:.1f}, "
                f"warnings={verdict.warnings}"
            )

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        cost_per_1k_tokens: float = 0.03,
        risk_threshold: float = 80.0,
        kill_on_error: bool = False,
        on_kill: Callable[[AgentBreakerVerdict], Any] | None = None,
        timeout: float = 10.0,
    ) -> None:
        super().__init__(
            agentbreaker_url,
            api_key,
            timeout=timeout,
            kill_on_error=kill_on_error,
        )
        self._cost_per_1k = cost_per_1k_tokens
        self._risk_threshold = risk_threshold
        self._on_kill = on_kill

    # -- public API ----------------------------------------------------------

    def protect(self, agent: Any, *, agent_id: str | None = None) -> "_ProtectedAzureAgent":
        """Wrap an Azure AI agent with kill-switch protection.

        Parameters
        ----------
        agent:
            Any object with an async ``run`` method (Azure AI Agent Service
            agent, Semantic Kernel agent, etc.).
        agent_id:
            Unique identifier for this agent.  If not provided, the agent's
            ``name`` attribute is used, or a UUID is generated.

        Returns
        -------
        _ProtectedAzureAgent
            A wrapper that behaves like the original agent but routes every
            step through AgentBreaker.
        """
        resolved_id = agent_id or getattr(agent, "name", None)
        if resolved_id is None:
            import uuid
            resolved_id = f"azure-agent-{uuid.uuid4().hex[:8]}"
        return _ProtectedAzureAgent(self, agent, resolved_id)

    async def on_agent_step(self, agent_id: str, step_data: dict) -> AgentBreakerVerdict:
        """Called after each agent step -- sends to AgentBreaker for analysis.

        Parameters
        ----------
        agent_id:
            Unique identifier for the agent.
        step_data:
            Dictionary containing at least ``input``, ``output``, and
            ``tokens``.  Optional keys: ``cost``, ``tool``, ``duration_ms``,
            ``context_size``.

        Returns
        -------
        AgentBreakerVerdict
            The kill/warn/allow decision from AgentBreaker.

        Raises
        ------
        AgentKilledException
            If the risk score exceeds the configured threshold.
        """
        tokens = step_data.get("tokens", 0)
        cost = step_data.get("cost", tokens / 1000 * self._cost_per_1k)

        verdict = await self._analyze_step(
            agent_id=agent_id,
            step_input=step_data.get("input", ""),
            step_output=step_data.get("output", ""),
            tokens=tokens,
            cost=cost,
            tool=step_data.get("tool"),
            duration_ms=step_data.get("duration_ms"),
            context_size=step_data.get("context_size"),
        )

        if verdict.action == "kill" or verdict.risk_score >= self._risk_threshold:
            if self._on_kill:
                maybe_coro = self._on_kill(verdict)
                if asyncio.iscoroutine(maybe_coro):
                    await maybe_coro
            raise self.AgentKilledException(verdict)

        return verdict


class _ProtectedAzureAgent:
    """Transparent wrapper around an Azure AI agent that monitors each step."""

    def __init__(
        self,
        middleware: AzureAgentBreakerMiddleware,
        inner_agent: Any,
        agent_id: str,
    ) -> None:
        self._middleware = middleware
        self._inner = inner_agent
        self._agent_id = agent_id
        self._step_count = 0

    async def run(self, *, input: str, **kwargs: Any) -> Any:
        """Execute the inner agent's ``run`` and analyse the result."""
        start = time.monotonic()
        result = await self._inner.run(input=input, **kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        self._step_count += 1

        output_text = str(result)
        tokens = getattr(result, "usage", {}).get("total_tokens", len(output_text) // 4)
        cost = getattr(result, "usage", {}).get("cost", tokens / 1000 * self._middleware._cost_per_1k)

        await self._middleware.on_agent_step(
            self._agent_id,
            {
                "input": input,
                "output": output_text,
                "tokens": tokens,
                "cost": cost,
                "duration_ms": elapsed_ms,
            },
        )
        return result

    def __getattr__(self, name: str) -> Any:
        """Proxy everything else to the inner agent."""
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# SemanticKernelPlugin
# ---------------------------------------------------------------------------

class SemanticKernelPlugin(_BaseIntegration):
    """AgentBreaker plugin for Microsoft Semantic Kernel.

    Registers as a Semantic Kernel plugin that monitors agent execution
    and triggers kills when spirals are detected.

    Usage::

        from semantic_kernel import Kernel
        from agentbreaker.integrations.azure import SemanticKernelPlugin

        kernel = Kernel()
        plugin = SemanticKernelPlugin(
            agentbreaker_url="https://your-agentbreaker.run.app",
            api_key="ab_live_xxx",
        )
        kernel.add_plugin(plugin, "agentbreaker")

        # Use the plugin's functions in your prompt orchestration
        # to gate agent actions on AgentBreaker analysis.

    The plugin exposes two Semantic Kernel functions:

    ``analyze_step``
        Send a step to AgentBreaker and return the verdict.
    ``should_continue``
        Returns ``True`` if the agent should continue, ``False`` if it
        should be halted.
    """

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        risk_threshold: float = 80.0,
        cost_per_1k_tokens: float = 0.03,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url,
            api_key,
            timeout=timeout,
            kill_on_error=kill_on_error,
        )
        self._risk_threshold = risk_threshold
        self._cost_per_1k = cost_per_1k_tokens
        self._verdicts: list[AgentBreakerVerdict] = []

    async def analyze_step(
        self,
        agent_id: str,
        step_input: str,
        step_output: str,
        tokens: int,
        cost: float | None = None,
        tool: str | None = None,
    ) -> AgentBreakerVerdict:
        """Semantic Kernel function: analyse a single agent step.

        Parameters
        ----------
        agent_id:
            Unique identifier for the agent in your Semantic Kernel setup.
        step_input / step_output:
            The prompt sent to the LLM and its response text.
        tokens:
            Total tokens consumed by this step.
        cost:
            Dollar cost.  If ``None``, estimated from *tokens*.
        tool:
            Name of the tool or plugin function invoked (if any).

        Returns
        -------
        AgentBreakerVerdict
        """
        resolved_cost = cost if cost is not None else tokens / 1000 * self._cost_per_1k
        verdict = await self._analyze_step(
            agent_id=agent_id,
            step_input=step_input,
            step_output=step_output,
            tokens=tokens,
            cost=resolved_cost,
            tool=tool,
        )
        self._verdicts.append(verdict)
        return verdict

    async def should_continue(self, agent_id: str) -> bool:
        """Semantic Kernel function: check whether the agent should keep running.

        Returns ``False`` if the latest verdict risk score exceeds the
        configured threshold or the action is ``kill``.
        """
        if not self._verdicts:
            return True
        latest = self._verdicts[-1]
        if latest.action == "kill" or latest.risk_score >= self._risk_threshold:
            logger.warning(
                "SemanticKernelPlugin: agent %s halted (risk=%.1f, action=%s)",
                agent_id,
                latest.risk_score,
                latest.action,
            )
            return False
        return True

    @property
    def verdict_history(self) -> list[AgentBreakerVerdict]:
        """Return all verdicts collected so far (useful for debugging)."""
        return list(self._verdicts)


# ---------------------------------------------------------------------------
# AutoGenMonitor
# ---------------------------------------------------------------------------

@dataclass
class _AutoGenAgentState:
    """Tracks per-agent state inside an AutoGen group chat."""
    agent_name: str
    total_tokens: int = 0
    total_cost: float = 0.0
    step_count: int = 0
    last_risk_score: float = 0.0


class AutoGenMonitor(_BaseIntegration):
    """Monitor for Microsoft AutoGen multi-agent conversations.

    Tracks token usage, output similarity, and cost across all agents
    in an AutoGen group chat.  When any agent's risk score crosses the
    threshold the entire conversation is flagged for termination.

    Usage::

        from autogen import GroupChatManager
        from agentbreaker.integrations.azure import AutoGenMonitor

        monitor = AutoGenMonitor(
            agentbreaker_url="https://your-agentbreaker.run.app",
            api_key="ab_live_xxx",
        )
        monitor.attach(group_chat_manager)

    Parameters
    ----------
    agentbreaker_url:
        Base URL of your AgentBreaker deployment.
    api_key:
        Project-scoped AgentBreaker API key.
    risk_threshold:
        Risk score above which the monitor flags for termination.
    aggregate_cost_limit:
        Maximum aggregate cost (USD) across all agents before a kill.
    cost_per_1k_tokens:
        Fallback cost rate.
    """

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        risk_threshold: float = 80.0,
        aggregate_cost_limit: float = 50.0,
        cost_per_1k_tokens: float = 0.03,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url,
            api_key,
            timeout=timeout,
            kill_on_error=kill_on_error,
        )
        self._risk_threshold = risk_threshold
        self._aggregate_cost_limit = aggregate_cost_limit
        self._cost_per_1k = cost_per_1k_tokens
        self._agents: dict[str, _AutoGenAgentState] = {}
        self._should_terminate = False
        self._termination_reason: str | None = None

    def attach(self, group_chat_manager: Any) -> None:
        """Attach to an AutoGen ``GroupChatManager``.

        Registers a reply hook so that every message flowing through the
        manager is analysed by AgentBreaker.

        Parameters
        ----------
        group_chat_manager:
            An instance of ``autogen.GroupChatManager``.
        """
        if hasattr(group_chat_manager, "register_reply"):
            group_chat_manager.register_reply(
                trigger=None,
                reply_func=self._autogen_reply_hook,
                position=0,
            )
            logger.info("AutoGenMonitor attached to GroupChatManager")
        else:
            logger.warning(
                "AutoGenMonitor: GroupChatManager does not expose "
                "register_reply -- manual integration required."
            )

    async def _autogen_reply_hook(
        self,
        recipient: Any,
        messages: list[dict],
        sender: Any,
        config: Any,
    ) -> tuple[bool, str | None]:
        """AutoGen reply hook -- called for each message in the group chat.

        Returns ``(True, reason)`` to terminate the conversation, or
        ``(False, None)`` to continue.
        """
        if self._should_terminate:
            return True, self._termination_reason

        if not messages:
            return False, None

        last_msg = messages[-1]
        agent_name = getattr(sender, "name", "unknown")
        content = last_msg.get("content", "")
        prev_content = messages[-2].get("content", "") if len(messages) >= 2 else ""

        tokens = last_msg.get("usage", {}).get("total_tokens", len(content) // 4)
        cost = last_msg.get("usage", {}).get("cost", tokens / 1000 * self._cost_per_1k)

        # Update per-agent state
        state = self._agents.setdefault(agent_name, _AutoGenAgentState(agent_name=agent_name))
        state.total_tokens += tokens
        state.total_cost += cost
        state.step_count += 1

        # Check aggregate cost
        total_cost = sum(s.total_cost for s in self._agents.values())
        if total_cost >= self._aggregate_cost_limit:
            self._should_terminate = True
            self._termination_reason = (
                f"AgentBreaker: aggregate cost ${total_cost:.2f} "
                f"exceeds limit ${self._aggregate_cost_limit:.2f}"
            )
            logger.warning(self._termination_reason)
            return True, self._termination_reason

        # Analyse step
        verdict = await self._analyze_step(
            agent_id=f"autogen-{agent_name}",
            step_input=prev_content,
            step_output=content,
            tokens=tokens,
            cost=cost,
        )
        state.last_risk_score = verdict.risk_score

        if verdict.action == "kill" or verdict.risk_score >= self._risk_threshold:
            self._should_terminate = True
            self._termination_reason = (
                f"AgentBreaker: agent '{agent_name}' risk={verdict.risk_score:.1f} "
                f"-- {', '.join(verdict.warnings)}"
            )
            logger.warning(self._termination_reason)
            return True, self._termination_reason

        return False, None

    @property
    def agent_states(self) -> dict[str, _AutoGenAgentState]:
        """Return a snapshot of per-agent tracking state."""
        return dict(self._agents)

    @property
    def aggregate_cost(self) -> float:
        """Return the total cost across all agents."""
        return sum(s.total_cost for s in self._agents.values())

    @property
    def should_terminate(self) -> bool:
        """Whether the conversation should be terminated."""
        return self._should_terminate
