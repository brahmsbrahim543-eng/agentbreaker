"""Playground service -- simulation loop with predefined scenarios."""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.detection.engine import DetectionEngine

_engine = DetectionEngine()

# --------------------------------------------------------------------------
# Predefined Scenarios
# --------------------------------------------------------------------------

SCENARIOS = {
    "semantic_loop": {
        "name": "Semantic Loop Detection",
        "description": (
            "An agent stuck in a loop, generating nearly identical outputs. "
            "The similarity detector catches it after ~8 steps."
        ),
        "steps": 12,
        "generator": "_gen_semantic_loop",
    },
    "cost_explosion": {
        "name": "Cost Explosion",
        "description": (
            "An agent whose token usage and cost grow exponentially. "
            "The cost velocity detector triggers a kill around step 10."
        ),
        "steps": 15,
        "generator": "_gen_cost_explosion",
    },
    "error_cascade": {
        "name": "Error Cascade",
        "description": (
            "An agent that encounters errors repeatedly and retries the same failing "
            "operation, wasting tokens. The error cascade detector fires after ~6 errors."
        ),
        "steps": 12,
        "generator": "_gen_error_cascade",
    },
}


def get_scenario_list() -> list[dict]:
    """Return scenario descriptions for the frontend."""
    return [
        {
            "id": key,
            "name": val["name"],
            "description": val["description"],
            "total_steps": val["steps"],
        }
        for key, val in SCENARIOS.items()
    ]


async def run_simulation(
    scenario_id: str,
    session_id: str,
    redis: aioredis.Redis,
) -> None:
    """Run a simulation scenario, publishing results to Redis in real time.

    Each step is generated at 1.5-second intervals and passed through the real
    detection engine. Results are published to the channel f"playground:{session_id}".
    """
    scenario = SCENARIOS.get(scenario_id)
    if scenario is None:
        await redis.publish(
            f"playground:{session_id}",
            json.dumps({"type": "error", "message": f"Unknown scenario: {scenario_id}"}),
        )
        return

    channel = f"playground:{session_id}"
    total_steps = scenario["steps"]
    gen_func = globals()[scenario["generator"]]

    # Publish start event
    await redis.publish(channel, json.dumps({
        "type": "start",
        "scenario": scenario_id,
        "total_steps": total_steps,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    all_steps: list[dict] = []

    for i in range(1, total_steps + 1):
        await asyncio.sleep(1.5)

        # Generate the step data
        step = gen_func(i, total_steps)
        all_steps.append(step)

        # Run through real detection engine
        analysis = await _engine.analyze_step(all_steps)

        event = {
            "type": "step",
            "step_number": i,
            "total_steps": total_steps,
            "step_data": {
                "input_preview": step.get("input_text", "")[:100],
                "output_preview": step.get("output_text", "")[:100],
                "tokens": step.get("tokens_used", 0),
                "cost": step.get("cost", 0.0),
                "error": step.get("error_message"),
            },
            "analysis": {
                "risk_score": analysis["score"],
                "action": analysis["action"],
                "breakdown": analysis["breakdown"],
                "warnings": analysis["warnings"],
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await redis.publish(channel, json.dumps(event))

        # Stop early if detection engine kills
        if analysis["action"] == "kill":
            await redis.publish(channel, json.dumps({
                "type": "kill",
                "step_number": i,
                "risk_score": analysis["score"],
                "reason": "; ".join(analysis["warnings"]) or "Risk threshold exceeded",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
            break

    # Publish completion event
    await redis.publish(channel, json.dumps({
        "type": "complete",
        "total_steps_run": len(all_steps),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))


# --------------------------------------------------------------------------
# Step generators
# --------------------------------------------------------------------------

def _gen_semantic_loop(step_num: int, total: int) -> dict:
    """Generate a step for the semantic loop scenario."""
    base_output = "I'll help you with that task. Let me analyze the data and provide recommendations."

    if step_num <= 3:
        # Normal varied outputs initially
        outputs = [
            "Starting analysis of the provided dataset. Found 1500 records to process.",
            "Processing records. Identified 3 key patterns in the data distribution.",
            "Generated initial report with findings. Token distribution shows normal variance.",
        ]
        output = outputs[step_num - 1]
    else:
        # Increasingly similar outputs
        slight_variations = [
            "I'll analyze the data again. The results show similar patterns as before.",
            "Re-analyzing the dataset. The patterns remain consistent with previous findings.",
            "Running another analysis pass. Results are largely unchanged from the prior run.",
            "Performing analysis once more. The data continues to show the same patterns.",
            "Analyzing the data set again. Findings are consistent with all previous iterations.",
        ]
        idx = (step_num - 4) % len(slight_variations)
        output = slight_variations[idx]

    return {
        "input_text": f"Step {step_num}: Please analyze the data and provide recommendations.",
        "output_text": output,
        "tokens_used": random.randint(800, 1200),
        "cost": round(random.uniform(0.01, 0.03), 4),
        "tool_name": None,
        "duration_ms": random.randint(500, 1500),
        "context_size": 4000 + step_num * 200,
        "error_message": None,
    }


def _gen_cost_explosion(step_num: int, total: int) -> dict:
    """Generate a step for the cost explosion scenario."""
    # Exponential growth in tokens and cost
    base_tokens = 500
    multiplier = 1.6 ** step_num
    tokens = int(base_tokens * multiplier)
    cost = round(tokens * 0.00003, 4)

    return {
        "input_text": f"Step {step_num}: Process this expanded context with all prior data included.",
        "output_text": f"Processing complete. Handled {tokens} tokens worth of data. "
                       f"Context window is at {min(95, 40 + step_num * 5)}% capacity.",
        "tokens_used": tokens,
        "cost": cost,
        "tool_name": "data_processor",
        "duration_ms": int(500 + tokens * 0.5),
        "context_size": int(4000 * multiplier),
        "error_message": None,
    }


def _gen_error_cascade(step_num: int, total: int) -> dict:
    """Generate a step for the error cascade scenario."""
    if step_num <= 3:
        # Normal steps first
        return {
            "input_text": f"Step {step_num}: Connect to external API and fetch user data.",
            "output_text": f"Successfully fetched data batch {step_num}. Retrieved 50 records.",
            "tokens_used": random.randint(600, 900),
            "cost": round(random.uniform(0.01, 0.02), 4),
            "tool_name": "api_connector",
            "duration_ms": random.randint(800, 2000),
            "context_size": 4000 + step_num * 300,
            "error_message": None,
        }
    else:
        # Errors start happening
        error_messages = [
            "ConnectionError: Failed to connect to api.example.com:443 (timeout after 30s)",
            "HTTPError: 503 Service Unavailable - rate limit exceeded",
            "ConnectionError: Connection refused by remote host",
            "TimeoutError: Request timed out after 60 seconds",
            "HTTPError: 429 Too Many Requests - retry after 120s",
        ]
        error = error_messages[(step_num - 4) % len(error_messages)]

        return {
            "input_text": f"Step {step_num}: Retry connecting to external API (attempt {step_num - 3}).",
            "output_text": f"Retrying API connection... Failed. Will try again with exponential backoff.",
            "tokens_used": random.randint(400, 700),
            "cost": round(random.uniform(0.008, 0.015), 4),
            "tool_name": "api_connector",
            "duration_ms": random.randint(30000, 60000),
            "context_size": 4000 + step_num * 500,
            "error_message": error,
        }
