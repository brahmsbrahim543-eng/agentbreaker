"""Core AgentBreaker client for tracking and killing runaway AI agents."""

from __future__ import annotations

import time
from typing import Any

import httpx

from .exceptions import AgentBreakerAPIError, AgentKilledError
from .types import StepResult

_MAX_RETRIES = 3


class AgentBreaker:
    """Client for the AgentBreaker real-time agent monitoring API.

    Tracks each step an AI agent takes, receives a risk assessment, and
    raises :class:`AgentKilledError` when the agent should be stopped.

    Example::

        with AgentBreaker(api_key="ab_live_xxx") as ab:
            result = ab.track_step(
                agent_id="order-bot",
                input="Find cheapest flight",
                output="Searching flights...",
                tokens=150,
                cost=0.004,
            )
            print(result.risk_score)

    Args:
        api_key: Your API key (format: ``ab_live_xxx`` or ``ab_test_xxx``).
        base_url: AgentBreaker API URL. Defaults to ``http://localhost:8000``
            for local development.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://agentbreaker-api.onrender.com",
        timeout: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key must not be empty")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
            timeout=timeout,
        )

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #

    def track_step(
        self,
        agent_id: str,
        input: str,
        output: str,
        tokens: int,
        cost: float,
        tool: str | None = None,
        duration_ms: int | None = None,
        context_size: int | None = None,
        error_message: str | None = None,
    ) -> StepResult:
        """Track a single agent step and receive a risk assessment.

        Args:
            agent_id: Unique identifier for the agent session.
            input: The prompt or input given to the agent at this step.
            output: The agent's response or output.
            tokens: Number of tokens consumed.
            cost: Dollar cost of this step.
            tool: Name of the tool invoked, if any.
            duration_ms: Wall-clock duration of the step in milliseconds.
            context_size: Current context window usage in tokens.
            error_message: Error string if the step failed.

        Returns:
            A :class:`StepResult` with the risk score and recommended action.

        Raises:
            AgentKilledError: If the risk engine decides the agent must stop.
            AgentBreakerAPIError: On non-200 API responses or connectivity
                failures after retries.
        """
        payload: dict[str, Any] = {
            "agent_id": agent_id,
            "input": input,
            "output": output,
            "tokens": tokens,
            "cost": cost,
        }
        if tool is not None:
            payload["tool"] = tool
        if duration_ms is not None:
            payload["duration_ms"] = duration_ms
        if context_size is not None:
            payload["context_size"] = context_size
        if error_message is not None:
            payload["error_message"] = error_message

        response = self._post_with_retry("/api/v1/ingest/step", payload)

        if response.status_code != 200:
            raise AgentBreakerAPIError(response.status_code, response.text)

        data: dict[str, Any] = response.json()
        result = StepResult(
            step_number=data["step_number"],
            risk_score=data["risk_score"],
            risk_breakdown=data["risk_breakdown"],
            action=data["action"],
            warnings=data.get("warnings", []),
            carbon_impact=data.get("carbon_impact"),
        )

        if result.action == "kill":
            raise AgentKilledError(
                agent_id=agent_id,
                reason=(
                    result.warnings[0]
                    if result.warnings
                    else "Risk threshold exceeded"
                ),
                cost_avoided=0.0,
                co2_avoided=(
                    result.carbon_impact.get("co2_grams", 0.0)
                    if result.carbon_impact
                    else 0.0
                ),
                risk_score=result.risk_score,
            )

        return result

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "AgentBreaker":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # --------------------------------------------------------------------- #
    # Internals
    # --------------------------------------------------------------------- #

    def _post_with_retry(
        self, path: str, payload: dict[str, Any]
    ) -> httpx.Response:
        """POST with exponential back-off (up to *_MAX_RETRIES* attempts)."""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return self._client.post(path, json=payload)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(2**attempt)
        raise AgentBreakerAPIError(
            0, f"Failed to connect after {_MAX_RETRIES} attempts: {last_exc}"
        )
