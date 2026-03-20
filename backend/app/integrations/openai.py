"""OpenAI Agents SDK Integration.

Works with the OpenAI Agents SDK (formerly Swarm) to monitor
agent execution and prevent cost overruns.

The OpenAI Agents SDK uses a declarative approach: you define agents with
instructions and tools, then hand off between them.  AgentBreaker hooks
into the SDK's lifecycle to monitor every LLM call and tool invocation.

Usage::

    from agents import Agent, Runner
    from agentbreaker.integrations.openai import OpenAIAgentGuard

    guard = OpenAIAgentGuard(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    agent = Agent(name="support-agent", instructions="You are a helpful agent.")

    # Option 1: Wrap the runner
    result = await guard.run(agent, input="Help me with my order")

    # Option 2: Use as a lifecycle hook
    guard.instrument(agent)
    result = await Runner.run(agent, input="Help me with my order")
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

logger = logging.getLogger("agentbreaker.integrations.openai")


# ---------------------------------------------------------------------------
# Verdict model
# ---------------------------------------------------------------------------

@dataclass
class AgentBreakerVerdict:
    """Result from the AgentBreaker analysis API."""

    step_number: int
    risk_score: float
    action: str
    warnings: list[str]
    risk_breakdown: dict[str, float]
    carbon_impact: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Per-run tracking
# ---------------------------------------------------------------------------

@dataclass
class AgentRunStats:
    """Accumulated statistics for a single agent run."""

    agent_name: str
    steps: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    peak_risk: float = 0.0
    handoffs: int = 0
    tool_calls: int = 0
    verdicts: list[AgentBreakerVerdict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# OpenAIAgentGuard
# ---------------------------------------------------------------------------

class OpenAIAgentGuard:
    """Guard for the OpenAI Agents SDK.

    Monitors agent execution (LLM calls, tool invocations, handoffs) and
    enforces cost and risk limits through the AgentBreaker API.

    Parameters
    ----------
    agentbreaker_url:
        Base URL of your AgentBreaker deployment.
    api_key:
        Project-scoped AgentBreaker API key.
    risk_threshold:
        Risk score (0--100) above which the agent is killed.
    cost_limit:
        Maximum cumulative cost per ``run()`` invocation.
    max_steps:
        Maximum number of LLM round-trips before forced termination.
    max_handoffs:
        Maximum agent-to-agent handoffs before forced termination.
        Prevents infinite delegation loops.
    cost_per_1k_tokens:
        Fallback cost rate when usage data is unavailable.
    on_kill:
        Optional async callback when an agent is killed.
    kill_on_error:
        If ``True``, treat AgentBreaker API failures as kill signals.
    """

    class AgentKilledException(Exception):
        """Raised when AgentBreaker terminates an OpenAI agent run."""

        def __init__(self, stats: AgentRunStats, reason: str) -> None:
            self.stats = stats
            super().__init__(
                f"AgentBreaker killed agent '{stats.agent_name}' after "
                f"{stats.steps} steps (${stats.total_cost:.4f}): {reason}"
            )

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        risk_threshold: float = 80.0,
        cost_limit: float = 25.0,
        max_steps: int = 100,
        max_handoffs: int = 20,
        cost_per_1k_tokens: float = 0.03,
        on_kill: Callable[[AgentRunStats, AgentBreakerVerdict], Any] | None = None,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        self._url = agentbreaker_url.rstrip("/")
        self._api_key = api_key
        self._risk_threshold = risk_threshold
        self._cost_limit = cost_limit
        self._max_steps = max_steps
        self._max_handoffs = max_handoffs
        self._cost_per_1k = cost_per_1k_tokens
        self._on_kill = on_kill
        self._timeout = timeout
        self._kill_on_error = kill_on_error
        self._client: httpx.AsyncClient | None = None
        self._runs: dict[str, AgentRunStats] = {}

    # -- lifecycle -----------------------------------------------------------

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._url,
                headers={
                    "X-API-Key": self._api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "agentbreaker-openai/1.0",
                },
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        """Shut down the HTTP connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # -- core analysis -------------------------------------------------------

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
    ) -> AgentBreakerVerdict:
        client = await self._ensure_client()
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "input": step_input,
            "output": step_output,
            "tokens": tokens,
            "cost": cost,
        }
        if tool:
            payload["tool"] = tool
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms

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
                    step_number=-1, risk_score=100.0, action="kill",
                    warnings=[f"AgentBreaker unreachable: {exc}"],
                    risk_breakdown={},
                )
            return AgentBreakerVerdict(
                step_number=-1, risk_score=0.0, action="allow",
                warnings=[f"AgentBreaker unreachable (fail-open): {exc}"],
                risk_breakdown={},
            )

    # -- public API: run wrapper ---------------------------------------------

    async def run(
        self,
        agent: Any,
        *,
        input: str,
        context: Any = None,
        max_turns: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """Run an OpenAI Agents SDK agent with AgentBreaker monitoring.

        This wraps ``Runner.run()`` and inspects each turn's usage data.

        Parameters
        ----------
        agent:
            An ``agents.Agent`` instance.
        input:
            User input string.
        context:
            Optional context object passed to the agent.
        max_turns:
            Maximum turns (applied by the SDK runner).

        Returns
        -------
        The ``RunResult`` from the SDK.

        Raises
        ------
        AgentKilledException
            If the run exceeds cost, step, handoff, or risk limits.
        """
        try:
            from agents import Runner
        except ImportError:
            raise ImportError(
                "The 'openai-agents' package is required. "
                "Install it with: pip install openai-agents"
            )

        agent_name = getattr(agent, "name", "openai-agent")
        stats = AgentRunStats(agent_name=agent_name)
        run_key = f"{agent_name}-{id(stats)}"
        self._runs[run_key] = stats

        run_kwargs: dict[str, Any] = {"input": input, **kwargs}
        if context is not None:
            run_kwargs["context"] = context
        if max_turns is not None:
            run_kwargs["max_turns"] = max_turns

        start = time.monotonic()
        result = await Runner.run(agent, **run_kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Extract usage from the result's raw responses
        raw_responses = getattr(result, "raw_responses", [])
        for resp in raw_responses:
            usage = getattr(resp, "usage", None)
            tokens = getattr(usage, "total_tokens", 0) if usage else 0
            cost = tokens / 1000 * self._cost_per_1k
            stats.steps += 1
            stats.total_tokens += tokens
            stats.total_cost += cost

        # Count handoffs
        new_items = getattr(result, "new_items", [])
        for item in new_items:
            item_type = getattr(item, "type", "")
            if "handoff" in str(item_type).lower():
                stats.handoffs += 1
            if "tool" in str(item_type).lower():
                stats.tool_calls += 1

        # Enforce limits
        if stats.steps > self._max_steps:
            await self._kill(stats, f"Step limit ({self._max_steps}) exceeded")
        if stats.handoffs > self._max_handoffs:
            await self._kill(stats, f"Handoff limit ({self._max_handoffs}) exceeded")
        if stats.total_cost > self._cost_limit:
            await self._kill(stats, f"Cost limit (${self._cost_limit:.2f}) exceeded")

        # Send aggregate step to AgentBreaker
        final_output = getattr(result, "final_output", str(result))
        verdict = await self._analyze_step(
            agent_id=agent_name,
            step_input=input,
            step_output=str(final_output),
            tokens=stats.total_tokens,
            cost=stats.total_cost,
            duration_ms=elapsed_ms,
        )
        stats.verdicts.append(verdict)
        stats.peak_risk = max(stats.peak_risk, verdict.risk_score)

        if verdict.action == "kill" or verdict.risk_score >= self._risk_threshold:
            await self._kill(stats, f"Risk score {verdict.risk_score:.1f}", verdict)

        return result

    async def _kill(
        self,
        stats: AgentRunStats,
        reason: str,
        verdict: AgentBreakerVerdict | None = None,
    ) -> None:
        """Trigger a kill: invoke callback and raise."""
        if self._on_kill and verdict:
            maybe_coro = self._on_kill(stats, verdict)
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
        raise self.AgentKilledException(stats, reason)

    # -- public API: instrument ----------------------------------------------

    def instrument(self, agent: Any) -> None:
        """Instrument an OpenAI Agent with AgentBreaker lifecycle hooks.

        Modifies the agent's tool definitions in-place so that each tool
        call is routed through AgentBreaker monitoring.

        Parameters
        ----------
        agent:
            An ``agents.Agent`` instance.
        """
        agent_name = getattr(agent, "name", "openai-agent")
        original_tools = getattr(agent, "tools", [])

        for i, tool in enumerate(original_tools):
            if callable(tool):
                original_fn = tool
                wrapped = self._wrap_tool(agent_name, original_fn)
                original_tools[i] = wrapped
                logger.debug("Instrumented tool %s on agent %s", getattr(tool, "__name__", i), agent_name)

        logger.info(
            "OpenAIAgentGuard: instrumented %d tools on agent '%s'",
            len(original_tools),
            agent_name,
        )

    def _wrap_tool(self, agent_name: str, fn: Callable) -> Callable:
        """Wrap a tool function with AgentBreaker monitoring."""
        guard = self

        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            tool_name = getattr(fn, "__name__", "unknown_tool")
            input_str = str(kwargs) if kwargs else str(args)
            start = time.monotonic()

            if asyncio.iscoroutinefunction(fn):
                result = await fn(*args, **kwargs)
            else:
                result = fn(*args, **kwargs)

            elapsed_ms = int((time.monotonic() - start) * 1000)
            output_str = str(result)
            tokens = len(output_str) // 4
            cost = tokens / 1000 * guard._cost_per_1k

            verdict = await guard._analyze_step(
                agent_id=agent_name,
                step_input=input_str,
                step_output=output_str,
                tokens=tokens,
                cost=cost,
                tool=tool_name,
                duration_ms=elapsed_ms,
            )

            if verdict.action == "kill" or verdict.risk_score >= guard._risk_threshold:
                raise guard.AgentKilledException(
                    AgentRunStats(agent_name=agent_name, peak_risk=verdict.risk_score),
                    f"Tool '{tool_name}' triggered kill -- risk={verdict.risk_score:.1f}",
                )

            return result

        wrapped.__name__ = getattr(fn, "__name__", "wrapped_tool")
        wrapped.__doc__ = getattr(fn, "__doc__", None)
        return wrapped

    # -- stats ---------------------------------------------------------------

    def get_run_stats(self) -> dict[str, AgentRunStats]:
        """Return all tracked run statistics."""
        return dict(self._runs)
