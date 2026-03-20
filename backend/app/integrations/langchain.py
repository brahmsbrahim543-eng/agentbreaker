"""LangChain Integration -- server-side agent monitoring.

Provides both callback-based and middleware-based integration
for LangChain agents, chains, and tools, as well as LangGraph
stateful agent workflows.

Usage with LangChain agents::

    from agentbreaker.integrations.langchain import LangChainAgentMonitor

    monitor = LangChainAgentMonitor(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    # As a LangChain callback handler
    agent.run("What is the weather?", callbacks=[monitor.as_callback()])

    # Or wrap an agent executor
    protected = monitor.wrap_agent(agent_executor)
    result = await protected.ainvoke({"input": "What is the weather?"})

Usage with LangGraph::

    from agentbreaker.integrations.langchain import LangGraphIntegration

    integration = LangGraphIntegration(
        agentbreaker_url="https://your-agentbreaker.run.app",
        api_key="ab_live_xxx",
    )

    # Add a guard node to your LangGraph workflow
    graph_builder.add_node("agentbreaker_guard", integration.guard_node)
    graph_builder.add_edge("agent", "agentbreaker_guard")
    graph_builder.add_conditional_edges(
        "agentbreaker_guard",
        integration.should_continue,
        {"continue": "agent", "end": END},
    )
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import httpx

logger = logging.getLogger("agentbreaker.integrations.langchain")


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

class _BaseLangChainIntegration:
    """Shared HTTP transport."""

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
                    "User-Agent": "agentbreaker-langchain/1.0",
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
# LangChain Callback Handler
# ---------------------------------------------------------------------------

class _AgentBreakerCallbackHandler:
    """LangChain-compatible callback handler.

    Implements the ``BaseCallbackHandler`` interface from ``langchain_core``
    without importing it -- so the integration works even if LangChain is
    not installed.  When LangChain *is* installed, this class duck-types
    correctly.

    This handler tracks:
    - LLM start/end (token counting)
    - Tool start/end (tool call monitoring)
    - Chain start/end (overall orchestration)
    """

    def __init__(
        self,
        monitor: LangChainAgentMonitor,
        agent_id: str,
    ) -> None:
        self._monitor = monitor
        self._agent_id = agent_id
        self._pending_input: str = ""
        self._pending_start: float = 0.0
        self._pending_tool: str | None = None

    # -- LLM callbacks -------------------------------------------------------

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Called when an LLM starts generating."""
        self._pending_input = prompts[0] if prompts else ""
        self._pending_start = time.monotonic()

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        """Called when an LLM finishes generating."""
        elapsed_ms = int((time.monotonic() - self._pending_start) * 1000)

        # Extract text from LLMResult
        generations = getattr(response, "generations", [[]])
        texts = []
        for gen_list in generations:
            for gen in gen_list:
                texts.append(getattr(gen, "text", str(gen)))
        output_text = "\n".join(texts)

        # Extract token usage
        llm_output = getattr(response, "llm_output", {}) or {}
        usage = llm_output.get("token_usage", {})
        tokens = usage.get("total_tokens", len(output_text) // 4)
        cost = tokens / 1000 * self._monitor._cost_per_1k

        # Fire-and-forget analysis (sync context, schedule async)
        asyncio.get_event_loop().create_task(
            self._monitor._on_step(
                agent_id=self._agent_id,
                step_input=self._pending_input,
                step_output=output_text,
                tokens=tokens,
                cost=cost,
                tool=self._pending_tool,
                duration_ms=elapsed_ms,
            )
        )
        self._pending_tool = None

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """Called when an LLM errors."""
        logger.warning("LLM error for agent %s: %s", self._agent_id, error)

    # -- Tool callbacks ------------------------------------------------------

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """Called when a tool starts execution."""
        self._pending_tool = serialized.get("name", "unknown_tool")
        self._pending_input = input_str
        self._pending_start = time.monotonic()

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Called when a tool finishes execution."""
        elapsed_ms = int((time.monotonic() - self._pending_start) * 1000)
        tokens = len(output) // 4
        cost = tokens / 1000 * self._monitor._cost_per_1k

        asyncio.get_event_loop().create_task(
            self._monitor._on_step(
                agent_id=self._agent_id,
                step_input=self._pending_input,
                step_output=output,
                tokens=tokens,
                cost=cost,
                tool=self._pending_tool,
                duration_ms=elapsed_ms,
            )
        )

    def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
        logger.warning("Tool error for agent %s: %s", self._agent_id, error)

    # -- Chain callbacks (no-ops for tracking) --------------------------------

    def on_chain_start(self, serialized: dict[str, Any], inputs: dict[str, Any], **kwargs: Any) -> None:
        pass

    def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any) -> None:
        pass

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        pass


# ---------------------------------------------------------------------------
# LangChainAgentMonitor
# ---------------------------------------------------------------------------

class LangChainAgentMonitor(_BaseLangChainIntegration):
    """Full-featured monitor for LangChain agents.

    Provides multiple integration points:

    1. **Callback handler** -- ``monitor.as_callback()`` returns a LangChain
       callback handler that you pass to ``agent.run(callbacks=[...])``.
    2. **Agent wrapper** -- ``monitor.wrap_agent(executor)`` returns a
       monitored wrapper around an ``AgentExecutor``.
    3. **Direct API** -- ``await monitor.analyze(...)`` sends a step
       manually.

    Parameters
    ----------
    agentbreaker_url / api_key:
        Connection to your AgentBreaker deployment.
    agent_id:
        Default agent identifier (can be overridden per-call).
    risk_threshold:
        Risk score above which the agent is killed.
    cost_limit:
        Maximum cumulative cost per agent session.
    cost_per_1k_tokens:
        Fallback token cost rate.
    on_kill:
        Optional async callback on agent kill.
    """

    class AgentKilledException(Exception):
        def __init__(self, agent_id: str, verdict: AgentBreakerVerdict) -> None:
            self.agent_id = agent_id
            self.verdict = verdict
            super().__init__(
                f"AgentBreaker killed LangChain agent '{agent_id}' "
                f"-- risk={verdict.risk_score:.1f}"
            )

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        agent_id: str = "langchain-agent",
        risk_threshold: float = 80.0,
        cost_limit: float = 25.0,
        cost_per_1k_tokens: float = 0.03,
        on_kill: Callable[[str, AgentBreakerVerdict], Any] | None = None,
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url, api_key,
            timeout=timeout, kill_on_error=kill_on_error,
        )
        self._default_agent_id = agent_id
        self._risk_threshold = risk_threshold
        self._cost_limit = cost_limit
        self._cost_per_1k = cost_per_1k_tokens
        self._on_kill = on_kill
        self._total_cost: float = 0.0
        self._verdicts: list[AgentBreakerVerdict] = []

    def as_callback(self, agent_id: str | None = None) -> _AgentBreakerCallbackHandler:
        """Return a LangChain callback handler.

        Parameters
        ----------
        agent_id:
            Override the default agent ID for this callback instance.

        Returns
        -------
        A callback handler compatible with LangChain's ``callbacks`` parameter.
        """
        return _AgentBreakerCallbackHandler(
            monitor=self,
            agent_id=agent_id or self._default_agent_id,
        )

    def wrap_agent(self, agent_executor: Any, *, agent_id: str | None = None) -> "_MonitoredAgentExecutor":
        """Wrap a LangChain ``AgentExecutor`` with AgentBreaker monitoring.

        Parameters
        ----------
        agent_executor:
            A LangChain ``AgentExecutor`` instance.
        agent_id:
            Override the default agent ID.

        Returns
        -------
        _MonitoredAgentExecutor
            A drop-in replacement with monitoring.
        """
        return _MonitoredAgentExecutor(
            monitor=self,
            inner=agent_executor,
            agent_id=agent_id or self._default_agent_id,
        )

    async def analyze(
        self,
        step_input: str,
        step_output: str,
        tokens: int,
        *,
        agent_id: str | None = None,
        cost: float | None = None,
        tool: str | None = None,
        duration_ms: int | None = None,
    ) -> AgentBreakerVerdict:
        """Directly analyse a step (for manual integration).

        Returns
        -------
        AgentBreakerVerdict

        Raises
        ------
        AgentKilledException
            If the risk score exceeds the threshold.
        """
        resolved_id = agent_id or self._default_agent_id
        resolved_cost = cost if cost is not None else tokens / 1000 * self._cost_per_1k

        verdict = await self._analyze_step(
            agent_id=resolved_id,
            step_input=step_input,
            step_output=step_output,
            tokens=tokens,
            cost=resolved_cost,
            tool=tool,
            duration_ms=duration_ms,
        )
        self._verdicts.append(verdict)
        self._total_cost += resolved_cost

        await self._check_limits(resolved_id, verdict)
        return verdict

    async def _on_step(
        self,
        agent_id: str,
        step_input: str,
        step_output: str,
        tokens: int,
        cost: float,
        tool: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Internal: called from the callback handler."""
        verdict = await self._analyze_step(
            agent_id=agent_id,
            step_input=step_input,
            step_output=step_output,
            tokens=tokens,
            cost=cost,
            tool=tool,
            duration_ms=duration_ms,
        )
        self._verdicts.append(verdict)
        self._total_cost += cost

        try:
            await self._check_limits(agent_id, verdict)
        except self.AgentKilledException:
            # In callback context we can only log -- the exception doesn't
            # propagate through LangChain's callback system.
            logger.error(
                "AgentBreaker would kill agent '%s' (risk=%.1f) but cannot "
                "propagate from callback context. Use wrap_agent() for hard kills.",
                agent_id,
                verdict.risk_score,
            )

    async def _check_limits(self, agent_id: str, verdict: AgentBreakerVerdict) -> None:
        """Enforce cost and risk limits."""
        if self._total_cost > self._cost_limit:
            verdict_override = AgentBreakerVerdict(
                step_number=verdict.step_number, risk_score=100.0, action="kill",
                warnings=[f"Cost limit (${self._cost_limit:.2f}) exceeded"],
                risk_breakdown=verdict.risk_breakdown,
            )
            await self._trigger_kill(agent_id, verdict_override)

        if verdict.action == "kill" or verdict.risk_score >= self._risk_threshold:
            await self._trigger_kill(agent_id, verdict)

    async def _trigger_kill(self, agent_id: str, verdict: AgentBreakerVerdict) -> None:
        if self._on_kill:
            maybe_coro = self._on_kill(agent_id, verdict)
            if asyncio.iscoroutine(maybe_coro):
                await maybe_coro
        raise self.AgentKilledException(agent_id, verdict)

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def verdict_history(self) -> list[AgentBreakerVerdict]:
        return list(self._verdicts)


class _MonitoredAgentExecutor:
    """Drop-in replacement for a LangChain AgentExecutor with monitoring."""

    def __init__(
        self,
        monitor: LangChainAgentMonitor,
        inner: Any,
        agent_id: str,
    ) -> None:
        self._monitor = monitor
        self._inner = inner
        self._agent_id = agent_id

    async def ainvoke(self, inputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Async invoke with monitoring."""
        start = time.monotonic()

        # Inject our callback
        callbacks = kwargs.pop("callbacks", []) or []
        callbacks.append(self._monitor.as_callback(self._agent_id))
        kwargs["callbacks"] = callbacks

        result = await self._inner.ainvoke(inputs, **kwargs)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Send final summary step
        input_text = inputs.get("input", str(inputs))
        output_text = result.get("output", str(result))
        tokens = len(output_text) // 4
        cost = tokens / 1000 * self._monitor._cost_per_1k

        await self._monitor.analyze(
            step_input=input_text,
            step_output=output_text,
            tokens=tokens,
            agent_id=self._agent_id,
            cost=cost,
            duration_ms=elapsed_ms,
        )

        return result

    def invoke(self, inputs: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        """Sync invoke -- delegates to ainvoke via event loop."""
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, self.ainvoke(inputs, **kwargs)).result()
        return loop.run_until_complete(self.ainvoke(inputs, **kwargs))

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# LangGraphIntegration
# ---------------------------------------------------------------------------

class LangGraphIntegration(_BaseLangChainIntegration):
    """Integration with LangGraph for stateful agent monitoring.

    LangGraph workflows are built as directed graphs of nodes.  This
    integration provides a **guard node** and a **conditional edge function**
    that you add to your graph to enforce cost and risk limits.

    Usage::

        from langgraph.graph import StateGraph, END
        from agentbreaker.integrations.langchain import LangGraphIntegration

        integration = LangGraphIntegration(
            agentbreaker_url="https://your-agentbreaker.run.app",
            api_key="ab_live_xxx",
        )

        # Define your state type
        class AgentState(TypedDict):
            messages: list
            agentbreaker_verdict: dict | None

        builder = StateGraph(AgentState)
        builder.add_node("agent", agent_node)
        builder.add_node("tools", tool_node)
        builder.add_node("agentbreaker_guard", integration.guard_node)

        # After the agent acts, check with AgentBreaker
        builder.add_edge("agent", "agentbreaker_guard")
        builder.add_conditional_edges(
            "agentbreaker_guard",
            integration.should_continue,
            {"continue": "tools", "end": END},
        )
        builder.add_edge("tools", "agent")

        graph = builder.compile()

    Parameters
    ----------
    agentbreaker_url / api_key:
        Connection to your AgentBreaker deployment.
    agent_id:
        Default agent identifier.
    risk_threshold:
        Risk score above which the guard halts the graph.
    cost_limit:
        Maximum cumulative cost before halting.
    cost_per_1k_tokens:
        Fallback token cost rate.
    state_messages_key:
        Key in the LangGraph state dict that holds the message list.
    state_verdict_key:
        Key in the state dict where the guard writes its verdict.
    """

    def __init__(
        self,
        agentbreaker_url: str,
        api_key: str,
        *,
        agent_id: str = "langgraph-agent",
        risk_threshold: float = 80.0,
        cost_limit: float = 25.0,
        cost_per_1k_tokens: float = 0.03,
        state_messages_key: str = "messages",
        state_verdict_key: str = "agentbreaker_verdict",
        timeout: float = 10.0,
        kill_on_error: bool = False,
    ) -> None:
        super().__init__(
            agentbreaker_url, api_key,
            timeout=timeout, kill_on_error=kill_on_error,
        )
        self._agent_id = agent_id
        self._risk_threshold = risk_threshold
        self._cost_limit = cost_limit
        self._cost_per_1k = cost_per_1k_tokens
        self._messages_key = state_messages_key
        self._verdict_key = state_verdict_key
        self._total_cost: float = 0.0
        self._step_count: int = 0

    async def guard_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """LangGraph node that sends the latest step to AgentBreaker.

        Reads the last two messages from the state (input/output pair),
        analyses them, and writes the verdict back into the state.

        Parameters
        ----------
        state:
            The LangGraph state dictionary.

        Returns
        -------
        Updated state with the AgentBreaker verdict.
        """
        messages = state.get(self._messages_key, [])
        if not messages:
            return {self._verdict_key: {"action": "allow", "risk_score": 0.0}}

        # Extract last message as output, second-to-last as input
        last_msg = messages[-1]
        prev_msg = messages[-2] if len(messages) >= 2 else None

        output_text = self._extract_message_text(last_msg)
        input_text = self._extract_message_text(prev_msg) if prev_msg else ""

        # Estimate tokens
        tokens = len(output_text) // 4
        cost = tokens / 1000 * self._cost_per_1k
        self._total_cost += cost
        self._step_count += 1

        # Extract tool info if available
        tool_name = None
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            tool_name = last_msg.tool_calls[0].get("name", None)
        elif isinstance(last_msg, dict) and "tool_calls" in last_msg:
            calls = last_msg["tool_calls"]
            if calls:
                tool_name = calls[0].get("name", None)

        verdict = await self._analyze_step(
            agent_id=self._agent_id,
            step_input=input_text,
            step_output=output_text,
            tokens=tokens,
            cost=cost,
            tool=tool_name,
        )

        verdict_dict = {
            "step_number": verdict.step_number,
            "risk_score": verdict.risk_score,
            "action": verdict.action,
            "warnings": verdict.warnings,
            "risk_breakdown": verdict.risk_breakdown,
            "total_cost": self._total_cost,
            "step_count": self._step_count,
        }

        # Force kill if cost limit exceeded
        if self._total_cost > self._cost_limit:
            verdict_dict["action"] = "kill"
            verdict_dict["warnings"] = [
                f"Cost limit (${self._cost_limit:.2f}) exceeded -- "
                f"spent ${self._total_cost:.2f}"
            ] + verdict_dict["warnings"]

        return {self._verdict_key: verdict_dict}

    def should_continue(self, state: dict[str, Any]) -> str:
        """LangGraph conditional edge: returns ``"continue"`` or ``"end"``.

        Use this as the condition function in ``add_conditional_edges``.

        Parameters
        ----------
        state:
            The LangGraph state dictionary (must contain the verdict key).

        Returns
        -------
        ``"continue"`` if the agent should keep running, ``"end"`` if it
        should be terminated.
        """
        verdict = state.get(self._verdict_key, {})
        action = verdict.get("action", "allow")
        risk_score = verdict.get("risk_score", 0.0)

        if action == "kill" or risk_score >= self._risk_threshold:
            logger.warning(
                "LangGraph guard: halting agent '%s' (action=%s, risk=%.1f, cost=$%.4f)",
                self._agent_id,
                action,
                risk_score,
                self._total_cost,
            )
            return "end"

        return "continue"

    @staticmethod
    def _extract_message_text(msg: Any) -> str:
        """Extract text content from a LangChain message object or dict."""
        if isinstance(msg, str):
            return msg
        if isinstance(msg, dict):
            return msg.get("content", str(msg))
        return getattr(msg, "content", str(msg))

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def step_count(self) -> int:
        return self._step_count

    def reset(self) -> None:
        """Reset cost and step counters (e.g. between graph invocations)."""
        self._total_cost = 0.0
        self._step_count = 0
