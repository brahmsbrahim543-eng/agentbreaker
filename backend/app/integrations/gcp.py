"""Google Vertex AI Integration -- AgentBreaker for Vertex AI Agent Builder.

Provides callbacks and middleware for:
- Vertex AI Agent Builder agents
- Vertex AI Extensions
- Google ADK (Agent Development Kit) agents
- Gemini-based agents

Usage with Vertex AI Agent Builder::

    from agentbreaker.integrations.gcp import VertexAgentBreakerCallback

    callback = VertexAgentBreakerCallback(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    # Pass as callback to Vertex AI agent
    agent.run(callbacks=[callback])

Usage with Gemini API::

    from agentbreaker.integrations.gcp import GeminiAgentMonitor

    monitor = GeminiAgentMonitor(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    # Wrap Gemini generate calls
    response = await monitor.generate(
        model="gemini-2.0-flash",
        agent_id="my-agent",
        contents=[...],
    )

Usage with Google ADK::

    from agentbreaker.integrations.gcp import ADKIntegration

    adk = ADKIntegration(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    # Register as before/after callbacks on the ADK runner
    runner = adk.wrap_runner(runner)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

logger = logging.getLogger("agentbreaker.integrations.gcp")


# ---------------------------------------------------------------------------
# Shared verdict model
# ---------------------------------------------------------------------------

@dataclass
class AgentBreakerVerdict:
    """Result returned by the AgentBreaker analysis API."""

    step_number: int
    risk_score: float
    action: str
    warnings: list[str]
    risk_breakdown: dict[str, float]
    carbon_impact: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Base transport
# ---------------------------------------------------------------------------

class _BaseGCPIntegration:
    """Shared HTTP transport for all GCP integration classes."""

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

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._url,
                headers={
                    "X-API-Key": self._api_key,
                    "Content-Type": "application/json",
                    "User-Agent": "agentbreaker-gcp/1.0",
                },
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
        """Cleanly shut down the HTTP connection pool."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

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
        """Send a step to ``/api/v1/ingest/step`` and return the verdict."""
        client = await self._ensure_client()

        payload: dict[str, Any] = {
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
                    step_number=-1, risk_score=100.0, action="kill",
                    warnings=[f"AgentBreaker unreachable: {exc}"],
                    risk_breakdown={},
                )
            return AgentBreakerVerdict(
                step_number=-1, risk_score=0.0, action="allow",
                warnings=[f"AgentBreaker unreachable (fail-open): {exc}"],
                risk_breakdown={},
            )


# ---------------------------------------------------------------------------
# VertexAgentBreakerCallback
# ---------------------------------------------------------------------------

class VertexAgentBreakerCallback(_BaseGCPIntegration):
    """Callback for Vertex AI Agent Builder.

    Implements the Vertex AI callback protocol so it can be passed directly
    to ``agent.run(callbacks=[callback])``.  Each agent turn is sent to the
    AgentBreaker API; if the risk score exceeds the threshold, the callback
    raises ``AgentKilledException`` to halt the agent.

    Parameters
    ----------
    agentbreaker_url:
        Base URL of your AgentBreaker deployment.
    api_key:
        Project-scoped AgentBreaker API key.
    risk_threshold:
        Risk score (0--100) above which the agent is killed.
    cost_per_1k_tokens:
        Fallback cost rate when the framework does not report cost.
    on_kill:
        Optional async callback invoked when an agent is killed.
    """

    class AgentKilledException(Exception):
        """Raised when AgentBreaker terminates a Vertex AI agent run."""

        def __init__(self, verdict: AgentBreakerVerdict) -> None:
            self.verdict = verdict
            super().__init__(
                f"AgentBreaker killed Vertex agent -- risk={verdict.risk_score:.1f}"
            )

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        risk_threshold: float = 80.0,
        cost_per_1k_tokens: float = 0.002,
        on_kill: Callable[[AgentBreakerVerdict], Any] | None = None,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url, api_key,
            timeout=timeout, kill_on_error=kill_on_error,
        )
        self._risk_threshold = risk_threshold
        self._cost_per_1k = cost_per_1k_tokens
        self._on_kill = on_kill
        self._verdicts: list[AgentBreakerVerdict] = []

    # -- Vertex AI callback protocol ----------------------------------------

    async def on_agent_action(
        self,
        agent_id: str,
        action: str,
        action_input: str,
        **kwargs: Any,
    ) -> None:
        """Called by Vertex AI Agent Builder before an agent takes an action.

        This hook is informational -- AgentBreaker does not block *before*
        the action.  It records the action for pairing with the output.
        """
        self._pending_input = action_input
        self._pending_tool = action
        self._pending_start = time.monotonic()

    async def on_agent_action_end(
        self,
        agent_id: str,
        output: str,
        *,
        tokens: int | None = None,
        cost: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Called by Vertex AI Agent Builder after an agent action completes.

        Sends the step to AgentBreaker and raises ``AgentKilledException``
        if the risk score exceeds the threshold.
        """
        elapsed_ms = int((time.monotonic() - getattr(self, "_pending_start", time.monotonic())) * 1000)
        resolved_tokens = tokens or len(output) // 4
        resolved_cost = cost if cost is not None else resolved_tokens / 1000 * self._cost_per_1k

        verdict = await self._analyze_step(
            agent_id=agent_id,
            step_input=getattr(self, "_pending_input", ""),
            step_output=output,
            tokens=resolved_tokens,
            cost=resolved_cost,
            tool=getattr(self, "_pending_tool", None),
            duration_ms=elapsed_ms,
        )
        self._verdicts.append(verdict)

        if verdict.action == "kill" or verdict.risk_score >= self._risk_threshold:
            if self._on_kill:
                maybe_coro = self._on_kill(verdict)
                if asyncio.iscoroutine(maybe_coro):
                    await maybe_coro
            raise self.AgentKilledException(verdict)

    async def on_agent_finish(self, agent_id: str, output: str, **kwargs: Any) -> None:
        """Called when the agent finishes its run (final answer)."""
        logger.info(
            "Vertex agent %s finished -- %d steps analysed, peak risk=%.1f",
            agent_id,
            len(self._verdicts),
            max((v.risk_score for v in self._verdicts), default=0.0),
        )

    @property
    def verdict_history(self) -> list[AgentBreakerVerdict]:
        """All verdicts collected during this agent run."""
        return list(self._verdicts)


# ---------------------------------------------------------------------------
# GeminiAgentMonitor
# ---------------------------------------------------------------------------

class GeminiAgentMonitor(_BaseGCPIntegration):
    """Monitor for Gemini-based agents using the Gemini API.

    Wraps ``google.genai`` calls so that every generate request is
    automatically analysed by AgentBreaker.

    Usage::

        monitor = GeminiAgentMonitor(
            agentbreaker_url="https://your-agentbreaker.run.app",
            api_key="ab_live_xxx",
        )

        # Direct generate with monitoring
        response = await monitor.generate(
            agent_id="my-gemini-agent",
            model="gemini-2.0-flash",
            contents="Summarise this document...",
        )

        # Or wrap an existing Gemini client
        monitored = monitor.wrap_client(genai_client, agent_id="my-agent")
        response = await monitored.generate_content(...)

    Parameters
    ----------
    agentbreaker_url / api_key:
        Connection to your AgentBreaker deployment.
    risk_threshold:
        Kill threshold.
    cost_per_1k_tokens:
        Gemini-specific cost rate.  Defaults to $0.002 (Flash pricing).
    """

    class AgentKilledException(Exception):
        def __init__(self, verdict: AgentBreakerVerdict) -> None:
            self.verdict = verdict
            super().__init__(f"AgentBreaker killed Gemini agent -- risk={verdict.risk_score:.1f}")

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        risk_threshold: float = 80.0,
        cost_per_1k_tokens: float = 0.002,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url, api_key,
            timeout=timeout, kill_on_error=kill_on_error,
        )
        self._risk_threshold = risk_threshold
        self._cost_per_1k = cost_per_1k_tokens
        self._session_verdicts: dict[str, list[AgentBreakerVerdict]] = {}

    async def generate(
        self,
        agent_id: str,
        model: str,
        contents: Any,
        *,
        gemini_client: Any | None = None,
        generation_config: dict | None = None,
    ) -> Any:
        """Execute a Gemini generate call with AgentBreaker monitoring.

        Parameters
        ----------
        agent_id:
            Unique identifier for this agent session.
        model:
            Gemini model name (e.g. ``gemini-2.0-flash``).
        contents:
            Prompt contents (string, list, or Gemini Content objects).
        gemini_client:
            An existing ``google.genai.Client`` instance.  If ``None``, you
            must have ``google-genai`` installed and configured.
        generation_config:
            Optional Gemini generation config.

        Returns
        -------
        The raw Gemini ``GenerateContentResponse``.

        Raises
        ------
        AgentKilledException
            If the risk score exceeds the threshold.
        """
        if gemini_client is None:
            try:
                from google import genai
                gemini_client = genai.Client()
            except ImportError:
                raise ImportError(
                    "google-genai is required for GeminiAgentMonitor.generate(). "
                    "Install it with: pip install google-genai"
                )

        input_text = str(contents)
        start = time.monotonic()

        kwargs: dict[str, Any] = {"model": model, "contents": contents}
        if generation_config:
            kwargs["config"] = generation_config

        response = await asyncio.to_thread(gemini_client.models.generate_content, **kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        output_text = response.text if hasattr(response, "text") else str(response)
        usage = getattr(response, "usage_metadata", None)
        tokens = getattr(usage, "total_token_count", len(output_text) // 4) if usage else len(output_text) // 4
        cost = tokens / 1000 * self._cost_per_1k

        verdict = await self._analyze_step(
            agent_id=agent_id,
            step_input=input_text,
            step_output=output_text,
            tokens=tokens,
            cost=cost,
            duration_ms=elapsed_ms,
            tool=model,
        )

        self._session_verdicts.setdefault(agent_id, []).append(verdict)

        if verdict.action == "kill" or verdict.risk_score >= self._risk_threshold:
            raise self.AgentKilledException(verdict)

        return response

    def wrap_client(self, gemini_client: Any, *, agent_id: str) -> "_MonitoredGeminiClient":
        """Return a drop-in wrapper around a ``google.genai.Client``.

        The wrapper's ``generate_content`` method routes through
        AgentBreaker analysis automatically.
        """
        return _MonitoredGeminiClient(self, gemini_client, agent_id)

    def get_session_verdicts(self, agent_id: str) -> list[AgentBreakerVerdict]:
        """Return all verdicts for a given agent session."""
        return list(self._session_verdicts.get(agent_id, []))


class _MonitoredGeminiClient:
    """Drop-in replacement for ``google.genai.Client`` with monitoring."""

    def __init__(
        self,
        monitor: GeminiAgentMonitor,
        inner: Any,
        agent_id: str,
    ) -> None:
        self._monitor = monitor
        self._inner = inner
        self._agent_id = agent_id

    async def generate_content(self, *, model: str, contents: Any, **kwargs: Any) -> Any:
        return await self._monitor.generate(
            agent_id=self._agent_id,
            model=model,
            contents=contents,
            gemini_client=self._inner,
            generation_config=kwargs.get("config"),
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# ADKIntegration
# ---------------------------------------------------------------------------

class ADKIntegration(_BaseGCPIntegration):
    """Integration with Google's Agent Development Kit (ADK).

    Hooks into the ADK runner lifecycle to monitor agent steps and enforce
    cost/risk limits.

    Usage::

        from agentbreaker.integrations.gcp import ADKIntegration

        adk = ADKIntegration(
            agentbreaker_url="https://your-agentbreaker.run.app",
            api_key="ab_live_xxx",
        )

        # Wrap an ADK runner
        runner = adk.wrap_runner(original_runner)
        await runner.run(user_message="...")

        # Or use as before/after hooks directly
        adk.register_hooks(agent)

    Parameters
    ----------
    agentbreaker_url / api_key:
        Connection to your AgentBreaker deployment.
    risk_threshold:
        Risk score above which the agent run is terminated.
    max_steps:
        Hard limit on the number of steps before forced termination.
    cost_limit:
        Maximum cumulative cost (USD) before forced termination.
    """

    class AgentKilledException(Exception):
        def __init__(self, reason: str, verdict: AgentBreakerVerdict | None = None) -> None:
            self.verdict = verdict
            super().__init__(reason)

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        risk_threshold: float = 80.0,
        max_steps: int = 100,
        cost_limit: float = 25.0,
        cost_per_1k_tokens: float = 0.002,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url, api_key,
            timeout=timeout, kill_on_error=kill_on_error,
        )
        self._risk_threshold = risk_threshold
        self._max_steps = max_steps
        self._cost_limit = cost_limit
        self._cost_per_1k = cost_per_1k_tokens
        self._step_count: int = 0
        self._total_cost: float = 0.0
        self._verdicts: list[AgentBreakerVerdict] = []

    def wrap_runner(self, runner: Any) -> "_MonitoredADKRunner":
        """Return a monitored wrapper around an ADK ``Runner``.

        The wrapper intercepts each ``run`` / ``run_async`` call, feeding
        steps into AgentBreaker and enforcing limits.
        """
        return _MonitoredADKRunner(self, runner)

    def register_hooks(self, agent: Any) -> None:
        """Register before/after tool-call hooks on an ADK agent.

        This is a lighter-weight alternative to ``wrap_runner`` for agents
        that support ``before_tool_callback`` and ``after_tool_callback``.
        """
        if hasattr(agent, "before_tool_callback"):
            original_before = agent.before_tool_callback

            async def before_hook(tool_name: str, tool_input: dict, **kw: Any) -> Any:
                self._pending_tool = tool_name
                self._pending_input = str(tool_input)
                self._pending_start = time.monotonic()
                if original_before:
                    return await original_before(tool_name, tool_input, **kw)

            agent.before_tool_callback = before_hook

        if hasattr(agent, "after_tool_callback"):
            original_after = agent.after_tool_callback

            async def after_hook(tool_name: str, tool_output: Any, **kw: Any) -> Any:
                elapsed_ms = int((time.monotonic() - getattr(self, "_pending_start", time.monotonic())) * 1000)
                output_str = str(tool_output)
                tokens = len(output_str) // 4
                cost = tokens / 1000 * self._cost_per_1k
                self._total_cost += cost
                self._step_count += 1

                if self._step_count > self._max_steps:
                    raise self.AgentKilledException(
                        f"AgentBreaker: max steps ({self._max_steps}) exceeded"
                    )
                if self._total_cost > self._cost_limit:
                    raise self.AgentKilledException(
                        f"AgentBreaker: cost limit (${self._cost_limit:.2f}) exceeded"
                    )

                agent_id = getattr(kw.get("agent"), "name", "adk-agent")
                verdict = await self._analyze_step(
                    agent_id=agent_id,
                    step_input=getattr(self, "_pending_input", ""),
                    step_output=output_str,
                    tokens=tokens,
                    cost=cost,
                    tool=tool_name,
                    duration_ms=elapsed_ms,
                )
                self._verdicts.append(verdict)

                if verdict.action == "kill" or verdict.risk_score >= self._risk_threshold:
                    raise self.AgentKilledException(
                        f"AgentBreaker: risk={verdict.risk_score:.1f}",
                        verdict=verdict,
                    )

                if original_after:
                    return await original_after(tool_name, tool_output, **kw)

            agent.after_tool_callback = after_hook

        logger.info("ADKIntegration: hooks registered on agent %s", getattr(agent, "name", "unknown"))

    @property
    def step_count(self) -> int:
        return self._step_count

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def verdict_history(self) -> list[AgentBreakerVerdict]:
        return list(self._verdicts)


class _MonitoredADKRunner:
    """Wrapper around an ADK runner that monitors execution."""

    def __init__(self, integration: ADKIntegration, inner: Any) -> None:
        self._integration = integration
        self._inner = inner

    async def run(self, *, user_message: str, **kwargs: Any) -> Any:
        """Run the ADK agent with monitoring."""
        start = time.monotonic()
        result = await self._inner.run(user_message=user_message, **kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        output_text = str(result)
        tokens = len(output_text) // 4
        cost = tokens / 1000 * self._integration._cost_per_1k
        self._integration._total_cost += cost
        self._integration._step_count += 1

        agent_id = getattr(self._inner, "agent_id", "adk-runner")
        verdict = await self._integration._analyze_step(
            agent_id=agent_id,
            step_input=user_message,
            step_output=output_text,
            tokens=tokens,
            cost=cost,
            duration_ms=elapsed_ms,
        )
        self._integration._verdicts.append(verdict)

        if verdict.action == "kill" or verdict.risk_score >= self._integration._risk_threshold:
            raise ADKIntegration.AgentKilledException(
                f"AgentBreaker: risk={verdict.risk_score:.1f}",
                verdict=verdict,
            )

        return result

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)
