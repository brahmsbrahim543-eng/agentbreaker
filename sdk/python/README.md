# AgentBreaker Python SDK

Real-time monitoring and kill-switch for AI agents. AgentBreaker detects runaway loops, cost spikes, and hallucination drift -- then stops the agent before damage is done.

## Installation

```bash
pip install agentbreaker
```

For LangChain integration:

```bash
pip install agentbreaker[langchain]
```

## Quick Start

```python
from agentbreaker import AgentBreaker, AgentKilledError

with AgentBreaker(api_key="ab_live_xxx", base_url="https://api.agentbreaker.dev") as ab:
    try:
        result = ab.track_step(
            agent_id="order-bot",
            input="Find cheapest flight to Paris",
            output="Searching 142 providers...",
            tokens=150,
            cost=0.004,
        )
        print(f"Risk: {result.risk_score:.2f} -> {result.action}")
    except AgentKilledError as e:
        print(f"Stopped: {e}")
```

## LangChain Integration

```python
from agentbreaker import AgentBreaker
from agentbreaker.callbacks import AgentBreakerCallback

ab = AgentBreaker(api_key="ab_live_xxx")
callback = AgentBreakerCallback(ab, agent_id="research-agent")

# Attach to any LangChain agent
agent.invoke(
    {"input": "Summarise Q4 earnings"},
    config={"callbacks": [callback]},
)
```

## API Reference

### `AgentBreaker(api_key, base_url="http://localhost:8000", timeout=30.0)`

Create a client. Use as a context manager or call `.close()` when done.

### `track_step(...) -> StepResult`

| Parameter      | Type         | Required | Description                        |
|----------------|--------------|----------|------------------------------------|
| `agent_id`     | `str`        | Yes      | Unique agent session identifier    |
| `input`        | `str`        | Yes      | Prompt or input for this step      |
| `output`       | `str`        | Yes      | Agent response or output           |
| `tokens`       | `int`        | Yes      | Tokens consumed                    |
| `cost`         | `float`      | Yes      | Dollar cost of this step           |
| `tool`         | `str | None` | No       | Tool name, if a tool was invoked   |
| `duration_ms`  | `int | None` | No       | Step wall-clock time (ms)          |
| `context_size` | `int | None` | No       | Current context window usage       |
| `error_message`| `str | None` | No       | Error string if the step failed    |

**Returns** a `StepResult` with:
- `step_number` (int)
- `risk_score` (float, 0.0 -- 1.0)
- `risk_breakdown` (dict)
- `action` (`"ok"` | `"warn"` | `"kill"`)
- `warnings` (list[str])
- `carbon_impact` (dict | None)

**Raises** `AgentKilledError` when the action is `"kill"`.

## Documentation

Full docs at [docs.agentbreaker.dev](https://docs.agentbreaker.dev).
