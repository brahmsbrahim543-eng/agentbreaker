"""
Import REAL agent traces from HuggingFace datasets into AgentBreaker.
Each step goes through the REAL 8-detector pipeline.
Sources:
- account4review/Agent-Trajectory-2.8k (2809 real programming agent trajectories)
"""

import sys
import os
import time
import random
import hashlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))

import httpx

API_KEY = "ab_live_0f50a377ad3d0221114569cabb3a7270"
BASE_URL = "http://127.0.0.1:8000"

# Realistic cost models for different agent types
COST_MODELS = {
    "gpt-4": {"cost_per_1k_input": 0.03, "cost_per_1k_output": 0.06},
    "gpt-4-turbo": {"cost_per_1k_input": 0.01, "cost_per_1k_output": 0.03},
    "claude-3-sonnet": {"cost_per_1k_input": 0.003, "cost_per_1k_output": 0.015},
    "gemini-pro": {"cost_per_1k_input": 0.00025, "cost_per_1k_output": 0.0005},
}

# Map agent types to realistic names
AGENT_NAMES = [
    "swe-agent-gpt4-{hash}",
    "code-repair-bot-{hash}",
    "bug-localizer-{hash}",
    "test-generator-{hash}",
    "pr-review-agent-{hash}",
    "refactor-assistant-{hash}",
    "security-scanner-{hash}",
    "dependency-checker-{hash}",
    "ci-debugger-{hash}",
    "doc-generator-{hash}",
    "migration-planner-{hash}",
    "perf-profiler-{hash}",
]


def estimate_tokens(text):
    """Rough token estimate: ~4 chars per token."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def get_cost(tokens, model_name="gpt-4-turbo", is_output=False):
    """Calculate cost based on model pricing."""
    model = COST_MODELS.get(model_name, COST_MODELS["gpt-4-turbo"])
    rate = model["cost_per_1k_output"] if is_output else model["cost_per_1k_input"]
    return (tokens / 1000) * rate


def extract_tool_name(content):
    """Extract tool name from agent messages."""
    if not content:
        return None
    if "<function=" in content:
        start = content.find("<function=") + len("<function=")
        end = content.find(">", start)
        if end > start:
            return content[start:end].strip()
    if "execute_bash" in content:
        return "bash"
    if "str_replace_editor" in content:
        return "editor"
    if "search" in content.lower()[:50]:
        return "search"
    return None


def has_error(content):
    """Check if step has an error."""
    if not content:
        return None
    error_indicators = [
        "Error:", "Traceback", "Exception", "FAILED",
        "error:", "CalledProcessError", "FileNotFoundError",
        "ModuleNotFoundError", "ImportError", "SyntaxError",
        "RuntimeError", "TypeError", "ValueError",
    ]
    for indicator in error_indicators:
        if indicator in content[:500]:
            return content[:300]
    return None


def process_trajectory(row_idx, messages, client):
    """Process a single agent trajectory through AgentBreaker."""
    # Generate a unique agent name
    hash_val = hashlib.md5(str(row_idx).encode()).hexdigest()[:6]
    name_template = AGENT_NAMES[row_idx % len(AGENT_NAMES)]
    agent_id = name_template.format(hash=hash_val)

    # Pick a random model
    model_name = random.choice(list(COST_MODELS.keys()))

    # Filter to assistant/user pairs (skip system message)
    steps = []
    for i in range(1, len(messages) - 1, 2):
        if i + 1 < len(messages):
            user_msg = messages[i]
            assistant_msg = messages[i + 1]
            if user_msg.get("role") == "user" and assistant_msg.get("role") == "assistant":
                steps.append((user_msg.get("content", ""), assistant_msg.get("content", "")))

    if not steps:
        return 0

    # Limit to max 20 steps per agent to avoid overwhelming
    steps = steps[:20]

    context_size = 2000
    ingested = 0

    for step_idx, (input_text, output_text) in enumerate(steps):
        input_tokens = estimate_tokens(input_text)
        output_tokens = estimate_tokens(output_text)
        total_tokens = input_tokens + output_tokens
        cost = get_cost(input_tokens, model_name) + get_cost(output_tokens, model_name, is_output=True)

        context_size += total_tokens

        tool = extract_tool_name(output_text)
        error = has_error(output_text) if output_text else None

        # Truncate texts for API (keep meaningful content)
        input_truncated = input_text[:3000] if input_text else "No input"
        output_truncated = output_text[:3000] if output_text else "No output"

        step_data = {
            "agent_id": agent_id,
            "input": input_truncated,
            "output": output_truncated,
            "tokens": total_tokens,
            "cost": round(cost, 6),
            "tool": tool or model_name,
            "duration_ms": random.randint(500, 8000),
            "context_size": min(context_size, 128000),
        }
        if error:
            step_data["error_message"] = error[:500]

        try:
            result = client.post("/api/v1/ingest/step", json=step_data)
            if result.status_code == 200:
                data = result.json()
                action = data.get("action", "ok")
                score = data.get("risk_score", 0)
                ingested += 1

                if action == "kill":
                    print(f"  [KILL] {agent_id} step {step_idx+1} | Risk: {score:.1f}")
                    break
                elif action == "warn" and step_idx % 5 == 0:
                    print(f"  [WARN] {agent_id} step {step_idx+1} | Risk: {score:.1f}")
            else:
                if step_idx == 0:
                    print(f"  [ERR] {agent_id}: {result.status_code}")
                break
        except Exception as e:
            if step_idx == 0:
                print(f"  [ERR] {agent_id}: {e}")
            break

        # Small delay to not overload
        time.sleep(0.05)

    return ingested


def main():
    print("=" * 60)
    print("  AgentBreaker - Real Trace Import")
    print("  Source: HuggingFace Agent-Trajectory-2.8k")
    print("  2809 real programming agent trajectories")
    print("=" * 60)

    # Load dataset
    print("\nLoading dataset from HuggingFace...")
    from datasets import load_dataset
    ds = load_dataset("account4review/Agent-Trajectory-2.8k", split="train")
    print(f"Loaded {len(ds)} trajectories\n")

    client = httpx.Client(
        base_url=BASE_URL,
        headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
        timeout=30.0,
    )

    # Import a meaningful subset (200 agents for good dashboard data)
    MAX_AGENTS = 200
    total_steps = 0
    agents_imported = 0

    # Sample diverse trajectories (different lengths)
    indices = list(range(len(ds)))
    random.seed(2026)
    random.shuffle(indices)
    selected = indices[:MAX_AGENTS]

    for i, idx in enumerate(selected):
        messages = ds[idx]["messages"]
        if not messages or len(messages) < 4:
            continue

        steps = process_trajectory(idx, messages, client)
        total_steps += steps
        if steps > 0:
            agents_imported += 1

        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{MAX_AGENTS} | Agents: {agents_imported} | Steps: {total_steps}")

    client.close()

    print(f"\n{'=' * 60}")
    print(f"  Import complete!")
    print(f"  Agents imported: {agents_imported}")
    print(f"  Total steps processed: {total_steps}")
    print(f"  Each step analyzed by real 8-detector engine")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
