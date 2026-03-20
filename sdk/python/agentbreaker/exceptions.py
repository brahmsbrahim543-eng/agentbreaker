"""Exceptions raised by the AgentBreaker SDK."""

from __future__ import annotations


class AgentBreakerAPIError(Exception):
    """Raised when the AgentBreaker API returns a non-200 response.

    Attributes:
        status_code: HTTP status code (0 if the request never reached the server).
        message: Error detail from the server or a connectivity message.
    """

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"AgentBreaker API error {status_code}: {message}")


class AgentKilledError(Exception):
    """Raised when AgentBreaker decides the agent must be stopped.

    Catching this exception is the recommended way to handle a kill signal.
    The exception carries context about *why* the agent was killed and how
    much cost/carbon was avoided by stopping early.

    Attributes:
        agent_id: Identifier of the killed agent.
        reason: Human-readable explanation.
        cost_avoided: Estimated dollars saved by killing the agent.
        co2_avoided: Estimated grams of CO2 avoided.
        risk_score: The risk score that triggered the kill.
    """

    def __init__(
        self,
        agent_id: str,
        reason: str,
        cost_avoided: float,
        co2_avoided: float,
        risk_score: float,
    ) -> None:
        self.agent_id = agent_id
        self.reason = reason
        self.cost_avoided = cost_avoided
        self.co2_avoided = co2_avoided
        self.risk_score = risk_score
        super().__init__(str(self))

    def __str__(self) -> str:
        return (
            f"Agent {self.agent_id} killed: {self.reason}. "
            f"Saved ${self.cost_avoided:.2f}, {self.co2_avoided:.1f}g CO2"
        )
