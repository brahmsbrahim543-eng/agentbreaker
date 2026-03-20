# AgentBreaker Python SDK

[![PyPI version](https://img.shields.io/pypi/v/agentbreaker.svg)](https://pypi.org/project/agentbreaker/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Downloads](https://img.shields.io/pypi/dm/agentbreaker.svg)](https://pypi.org/project/agentbreaker/)

**Real-time circuit breaker for AI agents.** AgentBreaker monitors every step your agent takes across 8 detection dimensions — semantic loops, cost velocity, reasoning cycles, token entropy, goal drift, error cascades, context inflation, and diminishing returns — then kills the agent before it causes damage.

## Why AgentBreaker?

| Problem | Without AgentBreaker | With AgentBreaker |
|---------|---------------------|-------------------|
| Agent stuck in loop | Burns $500 before timeout | Killed at $0.12 |
| Hallucination spiral | 200 bad API calls | Stopped after 3 |
| Context window bloat | OOM crash, lost work | Graceful shutdown |
| Cost runaway | $2,400 overnight bill | $47 with auto-kill |

## Installation

```bash
pip install agentbreaker
```

With framework integrations:

```bash
pip install agentbreaker[langchain]   # LangChain/LangGraph
pip install agentbreaker[crewai]      # CrewAI
```

## Quick Start (5 lines)

```python
from agentbreaker import AgentBreaker

ab = AgentBreaker(api_key="ab_live_xxx")
result = ab.track_step(
    agent_id="order-bot",
    input="Find cheapest flight to Paris",
    output="Searching 142 providers...",
    tokens=150, cost=0.004,
)
# result.action -> "ok" | "warn" | "kill"
# result.risk_score -> 0.0 to 100.0
# result.risk_breakdown -> {"semantic_similarity": 12, "cost_velocity": 3, ...}
```

## 8 Detection Dimensions

AgentBreaker's proprietary engine analyzes each step across 8 orthogonal dimensions:

| # | Dimension | Algorithm | What It Catches |
|---|-----------|-----------|-----------------|
| 1 | **Semantic Similarity** | Cosine similarity (sentence-transformers) | Repetitive outputs, stuck loops |
| 2 | **Reasoning Loop** | Tarjan's SCC on thought graphs | Circular reasoning chains |
| 3 | **Goal Drift** | Semantic anchor divergence | Agent wandering off-task |
| 4 | **Error Cascade** | Consecutive failure tracking | Repeated error-retry spirals |
| 5 | **Cost Velocity** | Exponential growth detection | Runaway API spending |
| 6 | **Token Entropy** | Shannon entropy + zlib compression | Gibberish, degenerate output |
| 7 | **Context Inflation** | Window utilization monitoring | Context bloat before OOM |
| 8 | **Diminishing Returns** | Novelty ratio analysis | Agent producing no new value |

Each dimension scores 0-100. The composite score uses weighted aggregation with configurable thresholds:
- **< 50**: OK — agent is healthy
- **50-74**: WARN — elevated risk, monitor closely
- **>= 75**: KILL — circuit breaker trips, agent is terminated

## Framework Integrations

### LangChain / LangGraph

```python
from agentbreaker import AgentBreaker
from agentbreaker.callbacks import AgentBreakerCallback

ab = AgentBreaker(api_key="ab_live_xxx")
callback = AgentBreakerCallback(ab, agent_id="research-agent")

agent.invoke(
    {"input": "Summarise Q4 earnings"},
    config={"callbacks": [callback]},
)
```

### Generic Python (any framework)

```python
from agentbreaker import AgentBreaker, AgentKilledError

with AgentBreaker(api_key="ab_live_xxx") as ab:
    for step in my_agent.run():
        try:
            result = ab.track_step(
                agent_id="my-agent",
                input=step.prompt,
                output=step.response,
                tokens=step.tokens,
                cost=step.cost,
                tool=step.tool_name,
                context_size=step.ctx_tokens,
                error_message=step.error,
            )
            if result.action == "warn":
                logger.warning(f"Risk elevated: {result.risk_score}")
        except AgentKilledError as e:
            logger.critical(f"Agent killed: {e.reason}")
            logger.info(f"Cost avoided: ${e.cost_avoided:.2f}")
            logger.info(f"CO2 avoided: {e.co2_avoided:.1f}g")
            break
```

## Carbon-Aware Economics

Every kill event includes environmental impact data:

```python
except AgentKilledError as e:
    print(e.co2_avoided)     # grams of CO2 saved
    print(e.cost_avoided)    # dollars saved
    print(e.risk_score)      # composite risk at kill time
```

AgentBreaker calculates CO2 per inference using region-specific emission factors (gCO2/kWh) and GPU power consumption models.

## API Reference

### `AgentBreaker(api_key, base_url, timeout)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api_key` | `str` | required | API key (`ab_live_*` or `ab_test_*`) |
| `base_url` | `str` | `https://agentbreaker-api.onrender.com` | API endpoint |
| `timeout` | `float` | `30.0` | Request timeout (seconds) |

### `track_step(...) -> StepResult`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | `str` | Yes | Unique agent session ID |
| `input` | `str` | Yes | Step input/prompt |
| `output` | `str` | Yes | Step output/response |
| `tokens` | `int` | Yes | Tokens consumed |
| `cost` | `float` | Yes | Dollar cost |
| `tool` | `str` | No | Tool name if invoked |
| `duration_ms` | `int` | No | Step duration (ms) |
| `context_size` | `int` | No | Context window usage |
| `error_message` | `str` | No | Error if step failed |

### `StepResult`

| Field | Type | Description |
|-------|------|-------------|
| `step_number` | `int` | Sequential step count |
| `risk_score` | `float` | Composite risk (0-100) |
| `risk_breakdown` | `dict` | Per-dimension scores |
| `action` | `str` | `"ok"`, `"warn"`, or `"kill"` |
| `warnings` | `list[str]` | Human-readable warnings |
| `carbon_impact` | `dict` | CO2 and cost data |

### Exceptions

- **`AgentKilledError`** — Raised when risk >= kill threshold. Properties: `agent_id`, `reason`, `cost_avoided`, `co2_avoided`, `risk_score`
- **`AgentBreakerAPIError`** — Raised on API errors. Properties: `status_code`, `message`

## WebSocket Real-Time Feed

Connect to the WebSocket endpoint for live risk updates:

```python
import websockets
import json

async with websockets.connect(
    "wss://agentbreaker-api.onrender.com/api/v1/ws/org123"
) as ws:
    async for message in ws:
        event = json.loads(message)
        if event["type"] == "kill":
            print(f"Agent {event['agent_id']} killed! Score: {event['risk_score']}")
```

## Documentation

Full documentation: [agentbreaker-web.onrender.com/docs](https://agentbreaker-web.onrender.com/docs)

## License

MIT License. See [LICENSE](LICENSE) for details.
