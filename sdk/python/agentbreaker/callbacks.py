"""LangChain callback handler for AgentBreaker integration.

Install the optional dependency with::

    pip install agentbreaker[langchain]
"""

from __future__ import annotations

from typing import Any, Sequence

from langchain_core.agents import AgentAction
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from .client import AgentBreaker


class AgentBreakerCallback(BaseCallbackHandler):
    """LangChain callback that sends every agent step to AgentBreaker.

    The handler estimates token counts from response text length and
    calculates approximate cost using a configurable per-1k-token rate.
    When AgentBreaker returns a ``kill`` action the handler raises
    :class:`~agentbreaker.exceptions.AgentKilledError`, which propagates
    up and stops the LangChain agent.

    Example::

        from agentbreaker import AgentBreaker
        from agentbreaker.callbacks import AgentBreakerCallback

        ab = AgentBreaker(api_key="ab_live_xxx")
        callback = AgentBreakerCallback(ab, agent_id="my-agent")
        agent.invoke(
            {"input": "Book a flight"},
            config={"callbacks": [callback]},
        )

    Args:
        client: An initialised :class:`AgentBreaker` instance.
        agent_id: Unique identifier for the agent session being monitored.
        estimate_cost_per_1k: Dollar cost per 1 000 tokens used for rough
            cost estimation when exact billing data is unavailable.
    """

    def __init__(
        self,
        client: AgentBreaker,
        agent_id: str,
        estimate_cost_per_1k: float = 0.03,
    ) -> None:
        super().__init__()
        self.client = client
        self.agent_id = agent_id
        self.cost_per_1k = estimate_cost_per_1k
        self._last_input: str = ""
        self._last_tool: str | None = None
        self._step_tokens: int = 0

    # ------------------------------------------------------------------ #
    # LLM events
    # ------------------------------------------------------------------ #

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """Capture the prompt text for the current LLM invocation."""
        if prompts:
            self._last_input = prompts[0][:500]

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Estimate token usage from the LLM response."""
        try:
            text = response.generations[0][0].text
            # Rough heuristic: ~1.3 tokens per whitespace-delimited word.
            self._step_tokens = max(int(len(text.split()) * 2), 10)
        except (IndexError, AttributeError):
            self._step_tokens = 50

    # ------------------------------------------------------------------ #
    # Agent / tool events
    # ------------------------------------------------------------------ #

    def on_agent_action(self, action: AgentAction, **kwargs: Any) -> None:
        """Record which tool the agent is about to call."""
        self._last_tool = action.tool
        self._last_input = str(action.tool_input)[:500]

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Send the completed tool step to AgentBreaker for scoring.

        May raise :class:`~agentbreaker.exceptions.AgentKilledError` if the
        risk engine decides the agent must be stopped.
        """
        output_text = str(output)[:5000]
        tokens = self._step_tokens or max(int(len(output_text.split()) * 2), 10)
        cost = (tokens / 1000) * self.cost_per_1k

        # AgentKilledError propagates up and halts the LangChain agent.
        self.client.track_step(
            agent_id=self.agent_id,
            input=self._last_input,
            output=output_text,
            tokens=tokens,
            cost=cost,
            tool=self._last_tool,
        )

    def on_tool_error(
        self,
        error: BaseException,
        **kwargs: Any,
    ) -> None:
        """Report a tool-level error to AgentBreaker."""
        self.client.track_step(
            agent_id=self.agent_id,
            input=self._last_input,
            output="",
            tokens=0,
            cost=0.0,
            tool=self._last_tool,
            error_message=str(error)[:1000],
        )
