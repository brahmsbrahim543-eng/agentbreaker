"""Salesforce Einstein AI Integration -- AgentBreaker for Agentforce.

Provides integration with:
- Salesforce Agentforce agents
- Einstein AI Trust Layer
- Salesforce Flow orchestration
- MuleSoft API governance

Usage::

    from agentbreaker.integrations.salesforce import AgentforceMonitor

    monitor = AgentforceMonitor(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    # Monitor an Agentforce agent session
    verdict = await monitor.on_agent_turn(
        agent_id="case-resolver-agent",
        turn_input="Customer says their order is late",
        turn_output="I'll check the order status using the tracking tool.",
        tokens=450,
    )

Usage with Einstein Trust Layer::

    from agentbreaker.integrations.salesforce import EinsteinTrustLayerPlugin

    plugin = EinsteinTrustLayerPlugin(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    # Register as a trust layer component
    trust_layer.register_plugin(plugin)

Usage with Salesforce Flow::

    from agentbreaker.integrations.salesforce import FlowOrchestrationGuard

    guard = FlowOrchestrationGuard(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    # Guard a flow that invokes AI agents
    result = await guard.execute_guarded_flow(flow_id, flow_inputs)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

import httpx

logger = logging.getLogger("agentbreaker.integrations.salesforce")


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
# Base transport
# ---------------------------------------------------------------------------

class _BaseSalesforceIntegration:
    """Shared HTTP transport for Salesforce integration classes."""

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
                    "User-Agent": "agentbreaker-salesforce/1.0",
                },
                timeout=self._timeout,
            )
        return self._client

    async def close(self) -> None:
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
# Agentforce session tracking
# ---------------------------------------------------------------------------

@dataclass
class AgentforceSession:
    """Tracks a single Agentforce agent conversation session."""

    session_id: str
    agent_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    turn_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    peak_risk_score: float = 0.0
    is_terminated: bool = False
    termination_reason: str | None = None
    verdicts: list[AgentBreakerVerdict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# AgentforceMonitor
# ---------------------------------------------------------------------------

class AgentforceMonitor(_BaseSalesforceIntegration):
    """Monitor for Salesforce Agentforce autonomous agents.

    Agentforce agents operate within Salesforce orgs, handling cases, leads,
    and other CRM workflows autonomously.  This monitor tracks each
    conversation turn and can terminate runaway sessions.

    The monitor maps Agentforce concepts to AgentBreaker:

    - **Agent session** maps to an AgentBreaker agent run
    - **Conversation turn** maps to an AgentBreaker step
    - **Topics and actions** map to AgentBreaker tool calls

    Parameters
    ----------
    agentbreaker_url / api_key:
        Connection to your AgentBreaker deployment.
    risk_threshold:
        Risk score above which the agent session is flagged for termination.
    session_cost_limit:
        Maximum cost (USD) per session before forced termination.
    cost_per_1k_tokens:
        Fallback token cost rate.
    on_kill:
        Optional async callback when a session is killed.
    """

    class SessionTerminated(Exception):
        """Raised when AgentBreaker terminates an Agentforce session."""

        def __init__(self, session: AgentforceSession, verdict: AgentBreakerVerdict) -> None:
            self.session = session
            self.verdict = verdict
            super().__init__(
                f"AgentBreaker terminated Agentforce session {session.session_id} "
                f"-- risk={verdict.risk_score:.1f}, turns={session.turn_count}"
            )

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        risk_threshold: float = 80.0,
        session_cost_limit: float = 10.0,
        cost_per_1k_tokens: float = 0.015,
        on_kill: Callable[[AgentforceSession, AgentBreakerVerdict], Any] | None = None,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url, api_key,
            timeout=timeout, kill_on_error=kill_on_error,
        )
        self._risk_threshold = risk_threshold
        self._session_cost_limit = session_cost_limit
        self._cost_per_1k = cost_per_1k_tokens
        self._on_kill = on_kill
        self._sessions: dict[str, AgentforceSession] = {}

    def start_session(self, session_id: str, agent_id: str) -> AgentforceSession:
        """Begin tracking a new Agentforce conversation session.

        Parameters
        ----------
        session_id:
            Salesforce session or conversation ID.
        agent_id:
            The Agentforce agent definition name.

        Returns
        -------
        AgentforceSession
        """
        session = AgentforceSession(session_id=session_id, agent_id=agent_id)
        self._sessions[session_id] = session
        logger.info("Agentforce session started: %s (agent=%s)", session_id, agent_id)
        return session

    async def on_agent_turn(
        self,
        agent_id: str,
        turn_input: str,
        turn_output: str,
        tokens: int,
        *,
        session_id: str | None = None,
        cost: float | None = None,
        topic: str | None = None,
        action: str | None = None,
        duration_ms: int | None = None,
    ) -> AgentBreakerVerdict:
        """Process a single Agentforce conversation turn.

        Parameters
        ----------
        agent_id:
            Agentforce agent identifier.
        turn_input:
            The user/system message that triggered this turn.
        turn_output:
            The agent's response.
        tokens:
            Tokens consumed by this turn.
        session_id:
            Optional session identifier.  If provided and a session exists,
            cumulative tracking is applied.
        cost:
            Dollar cost.  Estimated from tokens if not provided.
        topic:
            The Agentforce topic that handled this turn (e.g. "Order Management").
        action:
            The specific action taken (e.g. "Look Up Order Status").
        duration_ms:
            Latency of the turn in milliseconds.

        Returns
        -------
        AgentBreakerVerdict

        Raises
        ------
        SessionTerminated
            If the session exceeds cost or risk limits.
        """
        resolved_cost = cost if cost is not None else tokens / 1000 * self._cost_per_1k
        tool_name = f"{topic}/{action}" if topic and action else (topic or action)

        # Update session tracking
        session = self._sessions.get(session_id) if session_id else None
        if session:
            if session.is_terminated:
                raise self.SessionTerminated(
                    session,
                    session.verdicts[-1] if session.verdicts else AgentBreakerVerdict(
                        step_number=-1, risk_score=100.0, action="kill",
                        warnings=["Session already terminated"], risk_breakdown={},
                    ),
                )
            session.turn_count += 1
            session.total_tokens += tokens
            session.total_cost += resolved_cost

            if session.total_cost >= self._session_cost_limit:
                session.is_terminated = True
                session.termination_reason = (
                    f"Session cost ${session.total_cost:.2f} exceeds "
                    f"limit ${self._session_cost_limit:.2f}"
                )
                verdict = AgentBreakerVerdict(
                    step_number=session.turn_count, risk_score=100.0, action="kill",
                    warnings=[session.termination_reason], risk_breakdown={},
                )
                session.verdicts.append(verdict)
                raise self.SessionTerminated(session, verdict)

        # Analyse step
        verdict = await self._analyze_step(
            agent_id=agent_id,
            step_input=turn_input,
            step_output=turn_output,
            tokens=tokens,
            cost=resolved_cost,
            tool=tool_name,
            duration_ms=duration_ms,
        )

        if session:
            session.verdicts.append(verdict)
            session.peak_risk_score = max(session.peak_risk_score, verdict.risk_score)

        if verdict.action == "kill" or verdict.risk_score >= self._risk_threshold:
            if session:
                session.is_terminated = True
                session.termination_reason = (
                    f"Risk score {verdict.risk_score:.1f} exceeds threshold"
                )
            if self._on_kill and session:
                maybe_coro = self._on_kill(session, verdict)
                if asyncio.iscoroutine(maybe_coro):
                    await maybe_coro
            if session:
                raise self.SessionTerminated(session, verdict)

        return verdict

    def get_session(self, session_id: str) -> AgentforceSession | None:
        """Retrieve a tracked session by ID."""
        return self._sessions.get(session_id)

    @property
    def active_sessions(self) -> list[AgentforceSession]:
        """Return all sessions that have not been terminated."""
        return [s for s in self._sessions.values() if not s.is_terminated]

    @property
    def aggregate_cost(self) -> float:
        """Total cost across all sessions."""
        return sum(s.total_cost for s in self._sessions.values())


# ---------------------------------------------------------------------------
# EinsteinTrustLayerPlugin
# ---------------------------------------------------------------------------

class EinsteinTrustLayerPlugin(_BaseSalesforceIntegration):
    """Plugin for the Einstein AI Trust Layer.

    AgentBreaker integrates as a trust layer component, providing cost
    governance alongside the Trust Layer's built-in safety and grounding
    checks.

    The Trust Layer evaluates each LLM interaction along multiple axes:
    safety, grounding, toxicity, PII masking.  AgentBreaker adds a sixth
    axis: **cost governance** -- detecting when an agent is spiralling into
    expensive, repetitive, or unproductive loops.

    Usage::

        plugin = EinsteinTrustLayerPlugin(
            agentbreaker_url="https://your-agentbreaker.run.app",
            api_key="ab_live_xxx",
        )

        # Evaluate a prompt/response pair through the cost governance lens
        result = await plugin.evaluate(
            agent_id="case-agent",
            prompt="Help the customer with...",
            response="I'll look up the order...",
            tokens=380,
        )

        if result.should_block:
            # The Trust Layer should block this interaction
            ...

    Parameters
    ----------
    agentbreaker_url / api_key:
        Connection to your AgentBreaker deployment.
    risk_threshold:
        Risk score above which ``should_block`` returns ``True``.
    """

    @dataclass
    class TrustEvaluation:
        """Result of a Trust Layer cost governance evaluation."""

        should_block: bool
        risk_score: float
        governance_signals: dict[str, Any]
        warnings: list[str]
        verdict: AgentBreakerVerdict

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        risk_threshold: float = 80.0,
        cost_per_1k_tokens: float = 0.015,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url, api_key,
            timeout=timeout, kill_on_error=kill_on_error,
        )
        self._risk_threshold = risk_threshold
        self._cost_per_1k = cost_per_1k_tokens

    async def evaluate(
        self,
        agent_id: str,
        prompt: str,
        response: str,
        tokens: int,
        *,
        cost: float | None = None,
        tool: str | None = None,
    ) -> TrustEvaluation:
        """Evaluate a prompt/response pair for cost governance.

        This method is designed to be called from within the Einstein Trust
        Layer pipeline, alongside safety and grounding checks.

        Parameters
        ----------
        agent_id:
            Identifier of the agent or model configuration.
        prompt:
            The prompt sent to the LLM.
        response:
            The LLM's response.
        tokens:
            Total tokens consumed.
        cost:
            Dollar cost (estimated from tokens if absent).
        tool:
            Tool or action name (if applicable).

        Returns
        -------
        TrustEvaluation
            Contains ``should_block``, ``risk_score``, and detailed signals.
        """
        resolved_cost = cost if cost is not None else tokens / 1000 * self._cost_per_1k

        verdict = await self._analyze_step(
            agent_id=agent_id,
            step_input=prompt,
            step_output=response,
            tokens=tokens,
            cost=resolved_cost,
            tool=tool,
        )

        should_block = verdict.action == "kill" or verdict.risk_score >= self._risk_threshold

        governance_signals = {
            "cost_governance_score": verdict.risk_score,
            "action": verdict.action,
            "risk_breakdown": verdict.risk_breakdown,
            "carbon_impact": verdict.carbon_impact,
            "provider": "agentbreaker",
            "evaluation_type": "cost_governance",
        }

        return self.TrustEvaluation(
            should_block=should_block,
            risk_score=verdict.risk_score,
            governance_signals=governance_signals,
            warnings=verdict.warnings,
            verdict=verdict,
        )

    async def health_check(self) -> dict[str, Any]:
        """Verify connectivity to AgentBreaker (for Trust Layer status checks).

        Returns
        -------
        dict
            ``{"status": "healthy", ...}`` or ``{"status": "unhealthy", ...}``.
        """
        client = await self._ensure_client()
        try:
            resp = await client.get("/health")
            resp.raise_for_status()
            return {"status": "healthy", "provider": "agentbreaker", "latency_ms": resp.elapsed.total_seconds() * 1000}
        except httpx.HTTPError as exc:
            return {"status": "unhealthy", "provider": "agentbreaker", "error": str(exc)}


# ---------------------------------------------------------------------------
# FlowOrchestrationGuard
# ---------------------------------------------------------------------------

class FlowOrchestrationGuard(_BaseSalesforceIntegration):
    """Guard for Salesforce Flow orchestrations that use AI agents.

    Salesforce Flows can invoke Agentforce agents as steps.  This guard
    wraps those invocations, tracking cumulative cost and risk across the
    entire orchestration and terminating if limits are breached.

    Usage::

        guard = FlowOrchestrationGuard(
            agentbreaker_url="https://your-agentbreaker.run.app",
            api_key="ab_live_xxx",
        )

        # Guard individual AI steps within a flow
        async def my_flow():
            step1 = await guard.guard_step(
                flow_id="Case_Resolution_Flow",
                step_name="classify_case",
                agent_id="classifier-agent",
                step_input="Customer complaint about billing",
                step_output="Category: Billing, Priority: High",
                tokens=200,
            )

            step2 = await guard.guard_step(
                flow_id="Case_Resolution_Flow",
                step_name="resolve_case",
                agent_id="resolver-agent",
                step_input="Resolve high-priority billing complaint",
                step_output="Applied credit of $50 to account",
                tokens=350,
            )

    Parameters
    ----------
    agentbreaker_url / api_key:
        Connection to your AgentBreaker deployment.
    risk_threshold:
        Risk score above which a flow step is blocked.
    flow_cost_limit:
        Maximum cumulative cost per flow execution.
    max_ai_steps:
        Maximum number of AI-powered steps per flow execution.
    """

    class FlowTerminated(Exception):
        """Raised when AgentBreaker terminates a Flow orchestration."""

        def __init__(self, flow_id: str, reason: str) -> None:
            self.flow_id = flow_id
            super().__init__(f"AgentBreaker terminated flow {flow_id}: {reason}")

    @dataclass
    class FlowExecution:
        """Tracks a single flow execution."""
        flow_id: str
        started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
        step_count: int = 0
        total_tokens: int = 0
        total_cost: float = 0.0
        peak_risk: float = 0.0
        steps: list[dict[str, Any]] = field(default_factory=list)

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        risk_threshold: float = 80.0,
        flow_cost_limit: float = 20.0,
        max_ai_steps: int = 50,
        cost_per_1k_tokens: float = 0.015,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url, api_key,
            timeout=timeout, kill_on_error=kill_on_error,
        )
        self._risk_threshold = risk_threshold
        self._flow_cost_limit = flow_cost_limit
        self._max_ai_steps = max_ai_steps
        self._cost_per_1k = cost_per_1k_tokens
        self._flows: dict[str, FlowOrchestrationGuard.FlowExecution] = {}

    async def guard_step(
        self,
        flow_id: str,
        step_name: str,
        agent_id: str,
        step_input: str,
        step_output: str,
        tokens: int,
        *,
        cost: float | None = None,
        duration_ms: int | None = None,
    ) -> AgentBreakerVerdict:
        """Guard a single AI step within a Flow orchestration.

        Parameters
        ----------
        flow_id:
            The Salesforce Flow API name or ID.
        step_name:
            Human-readable name of the current flow step.
        agent_id:
            The Agentforce agent invoked by this step.
        step_input / step_output:
            Input and output of the AI step.
        tokens:
            Tokens consumed.
        cost:
            Dollar cost (estimated if absent).
        duration_ms:
            Step latency.

        Returns
        -------
        AgentBreakerVerdict

        Raises
        ------
        FlowTerminated
            If the flow exceeds cost, step count, or risk limits.
        """
        resolved_cost = cost if cost is not None else tokens / 1000 * self._cost_per_1k

        # Track flow execution
        execution = self._flows.get(flow_id)
        if execution is None:
            execution = self.FlowExecution(flow_id=flow_id)
            self._flows[flow_id] = execution

        execution.step_count += 1
        execution.total_tokens += tokens
        execution.total_cost += resolved_cost

        # Enforce hard limits
        if execution.step_count > self._max_ai_steps:
            raise self.FlowTerminated(
                flow_id,
                f"AI step limit ({self._max_ai_steps}) exceeded",
            )
        if execution.total_cost > self._flow_cost_limit:
            raise self.FlowTerminated(
                flow_id,
                f"Cost limit (${self._flow_cost_limit:.2f}) exceeded "
                f"-- spent ${execution.total_cost:.2f}",
            )

        # Analyse step
        verdict = await self._analyze_step(
            agent_id=agent_id,
            step_input=step_input,
            step_output=step_output,
            tokens=tokens,
            cost=resolved_cost,
            tool=step_name,
            duration_ms=duration_ms,
        )

        execution.peak_risk = max(execution.peak_risk, verdict.risk_score)
        execution.steps.append({
            "step_name": step_name,
            "agent_id": agent_id,
            "tokens": tokens,
            "cost": resolved_cost,
            "risk_score": verdict.risk_score,
            "action": verdict.action,
        })

        if verdict.action == "kill" or verdict.risk_score >= self._risk_threshold:
            raise self.FlowTerminated(
                flow_id,
                f"Risk score {verdict.risk_score:.1f} at step '{step_name}'",
            )

        return verdict

    def get_flow_execution(self, flow_id: str) -> FlowExecution | None:
        """Retrieve tracking data for a flow execution."""
        return self._flows.get(flow_id)

    def reset_flow(self, flow_id: str) -> None:
        """Clear tracking data for a flow (e.g. before a new execution)."""
        self._flows.pop(flow_id, None)
