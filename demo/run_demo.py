#!/usr/bin/env python3
"""AgentBreaker Live Demo -- watch agents get detected and killed in real-time.

Usage:
    python run_demo.py semantic_loop [--offline]
    python run_demo.py error_cascade [--offline]
    python run_demo.py cost_explosion [--offline]

The demo connects to a running AgentBreaker backend (default: http://localhost:8000)
and sends steps that simulate agent behavior. Watch the detection engine identify
the pattern and kill the agent.

Use --offline to use mock tools (no internet required).
"""

from __future__ import annotations

import argparse
import sys
import time
import os

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk", "python"))

from agentbreaker import AgentBreaker, AgentKilledError, AgentBreakerAPIError
from mock_tools import MockSearchTool, MockFailingTool, MockExpensiveTool

# ---------------------------------------------------------------------------
# ANSI colors
# ---------------------------------------------------------------------------
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"

# ---------------------------------------------------------------------------
# Search query variations for the semantic_loop scenario
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    "number of stars universe",
    "verify star count",
    "cross reference stars",
    "final verification star number",
    "how many stars exist total",
    "stars observable universe estimate",
    "recheck star count sources",
    "confirm astronomical star count",
    "double check star estimates",
    "stars in universe latest data",
]


def risk_bar(score: float, width: int = 10) -> str:
    """Render a visual risk bar using block characters."""
    filled = int(score / 100 * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def risk_color(score: float) -> str:
    """Return the ANSI color code for a given risk score."""
    if score >= 75:
        return RED
    if score >= 40:
        return YELLOW
    return GREEN


def action_label(action: str, score: float, warnings: list[str]) -> str:
    """Format the action label with color and optional details."""
    if action == "kill":
        detail = ""
        for w in warnings:
            if ":" in w:
                detail = f" -- {w}"
                break
        return f"{RED}KILLED{detail}{RESET}"
    if action == "warn":
        detail = ""
        for w in warnings:
            detail = f" -- {w}"
            break
        return f"{YELLOW}WARNING{detail}{RESET}"
    return f"{GREEN}OK{RESET}"


def print_header(title: str, description: str) -> None:
    """Print a scenario header."""
    line = "\u2550" * 55
    print(f"\n{CYAN}{line}{RESET}")
    print(f"{BOLD}{WHITE}  AgentBreaker Demo: {title}{RESET}")
    print(f"{DIM}  {description}{RESET}")
    print(f"{CYAN}{line}{RESET}\n")


def print_kill_summary(exc: AgentKilledError, elapsed: float, steps: int) -> None:
    """Print the post-kill summary box."""
    line = "\u2550" * 55
    print(f"\n{RED}{line}{RESET}")
    print(f"  {RED}{BOLD}AGENT KILLED{RESET} -- {exc.reason}")
    print(f"{RED}{line}{RESET}")
    print(f"  {CYAN}Cost avoided :{RESET}  ${exc.cost_avoided:.2f}")
    print(f"  {CYAN}CO2 avoided  :{RESET}  {exc.co2_avoided:.1f}g")
    print(f"  {CYAN}Killed after :{RESET}  {elapsed:.1f} seconds, {steps} steps")
    print(f"  {CYAN}Risk score   :{RESET}  {exc.risk_score:.0f}/100")
    print(f"{RED}{line}{RESET}\n")


def print_connection_error(exc: AgentBreakerAPIError) -> None:
    """Print a helpful message when the backend is unreachable."""
    line = "\u2550" * 55
    print(f"\n{RED}{line}{RESET}")
    print(f"  {RED}{BOLD}CONNECTION FAILED{RESET}")
    print(f"{RED}{line}{RESET}")
    print(f"  Could not reach the AgentBreaker backend.")
    print(f"  {DIM}Error: {exc.message}{RESET}")
    print()
    print(f"  Make sure the backend is running:")
    print(f"    {CYAN}cd ../backend && uvicorn main:app --reload{RESET}")
    print(f"  Or with Docker:")
    print(f"    {CYAN}cd .. && docker-compose up{RESET}")
    print(f"{RED}{line}{RESET}\n")


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------


def run_semantic_loop(ab: AgentBreaker) -> None:
    """Simulate an agent repeatedly searching for the same information."""
    print_header(
        "Semantic Loop Detection",
        "Agent keeps searching for 'number of stars' -- same answer, different words.",
    )

    mock_search = MockSearchTool(seed=42)
    agent_id = "star-counter-demo"
    start_time = time.time()
    steps_done = 0

    try:
        for i in range(10):
            query = SEARCH_QUERIES[i % len(SEARCH_QUERIES)]
            output = mock_search.run(query)

            # Truncate output for display
            display_output = output if len(output) <= 70 else output[:67] + "..."

            result = ab.track_step(
                agent_id=agent_id,
                input=f"search: {query}",
                output=output,
                tokens=150,
                cost=0.003,
                tool="web_search",
            )
            steps_done = result.step_number

            score = result.risk_score
            color = risk_color(score)
            bar = risk_bar(score)
            label = action_label(result.action, score, result.warnings)

            print(f"  {BOLD}[Step {result.step_number}]{RESET} {MAGENTA}search(\"{query}\"){RESET}")
            print(f"    {DIM}-> \"{display_output}\"{RESET}")
            print(f"    Risk: {color}{score:.0f}/100 {bar}{RESET}  {label}")
            print()

            time.sleep(1.5)

        # If we get here, agent was not killed
        elapsed = time.time() - start_time
        print(f"\n  {GREEN}Agent completed all steps without being killed.{RESET}")
        print(f"  {DIM}Elapsed: {elapsed:.1f}s, Steps: {steps_done}{RESET}\n")

    except AgentKilledError as exc:
        elapsed = time.time() - start_time
        print_kill_summary(exc, elapsed, steps_done)


def run_error_cascade(ab: AgentBreaker) -> None:
    """Simulate an agent retrying a failing API call indefinitely."""
    print_header(
        "Error Cascade Detection",
        "Agent keeps calling a broken pricing API -- same error every time.",
    )

    mock_api = MockFailingTool()
    agent_id = "pricing-bot-demo"
    start_time = time.time()
    steps_done = 0

    try:
        for i in range(10):
            # Try calling the tool -- it always fails
            error_msg = ""
            try:
                mock_api.run("get_price SKU-4419")
            except ConnectionError as e:
                error_msg = str(e)

            result = ab.track_step(
                agent_id=agent_id,
                input=f"pricing_api(SKU-4419) attempt {i + 1}",
                output="",
                tokens=80,
                cost=0.001,
                tool="pricing_api",
                error_message=error_msg,
            )
            steps_done = result.step_number

            score = result.risk_score
            color = risk_color(score)
            bar = risk_bar(score)
            label = action_label(result.action, score, result.warnings)

            # Truncate error for display
            display_err = error_msg if len(error_msg) <= 60 else error_msg[:57] + "..."

            print(f"  {BOLD}[Step {result.step_number}]{RESET} {RED}pricing_api(SKU-4419){RESET}")
            print(f"    {RED}ERROR: {display_err}{RESET}")
            print(f"    Risk: {color}{score:.0f}/100 {bar}{RESET}  {label}")
            print()

            time.sleep(1.0)

        elapsed = time.time() - start_time
        print(f"\n  {GREEN}Agent completed all steps without being killed.{RESET}")
        print(f"  {DIM}Elapsed: {elapsed:.1f}s, Steps: {steps_done}{RESET}\n")

    except AgentKilledError as exc:
        elapsed = time.time() - start_time
        print_kill_summary(exc, elapsed, steps_done)


def run_cost_explosion(ab: AgentBreaker) -> None:
    """Simulate an agent whose costs double with every step."""
    print_header(
        "Cost Explosion Detection",
        "Agent processes exponentially more data each step -- cost doubles every call.",
    )

    mock_tool = MockExpensiveTool()
    agent_id = "data-analyzer-demo"
    start_time = time.time()
    steps_done = 0

    try:
        for i in range(10):
            output = mock_tool.run("analyze_all")
            cost = 0.01 * (2 ** (i + 1))
            tokens = 200 * (2 ** i)

            # Truncate output for display
            display_output = output if len(output) <= 70 else output[:67] + "..."

            result = ab.track_step(
                agent_id=agent_id,
                input=f"analyze_database(depth={i + 1})",
                output=output,
                tokens=tokens,
                cost=cost,
                tool="database_analyzer",
            )
            steps_done = result.step_number

            score = result.risk_score
            color = risk_color(score)
            bar = risk_bar(score)
            label = action_label(result.action, score, result.warnings)

            print(f"  {BOLD}[Step {result.step_number}]{RESET} {MAGENTA}analyze_database(depth={i + 1}){RESET}")
            print(f"    {DIM}-> \"{display_output}\"{RESET}")
            print(f"    Cost this step: {CYAN}${cost:.4f}{RESET}  |  Tokens: {CYAN}{tokens:,}{RESET}")
            print(f"    Risk: {color}{score:.0f}/100 {bar}{RESET}  {label}")
            print()

            time.sleep(1.2)

        elapsed = time.time() - start_time
        print(f"\n  {GREEN}Agent completed all steps without being killed.{RESET}")
        print(f"  {DIM}Elapsed: {elapsed:.1f}s, Steps: {steps_done}{RESET}\n")

    except AgentKilledError as exc:
        elapsed = time.time() - start_time
        print_kill_summary(exc, elapsed, steps_done)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

SCENARIOS = {
    "semantic_loop": run_semantic_loop,
    "error_cascade": run_error_cascade,
    "cost_explosion": run_cost_explosion,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AgentBreaker Live Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Scenarios:\n"
            "  semantic_loop   Agent keeps searching for the same answer\n"
            "  error_cascade   Agent retries a broken API call endlessly\n"
            "  cost_explosion  Agent processes exponentially more data\n"
        ),
    )
    parser.add_argument(
        "scenario",
        choices=SCENARIOS.keys(),
        help="Which failure mode to demonstrate",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use mock tools only (no internet required)",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("AGENTBREAKER_API_KEY", "ab_test_demo_key"),
        help="AgentBreaker API key (default: ab_test_demo_key or $AGENTBREAKER_API_KEY)",
    )
    parser.add_argument(
        "--base-url",
        default=os.environ.get("AGENTBREAKER_URL", "http://localhost:8000"),
        help="AgentBreaker backend URL (default: http://localhost:8000 or $AGENTBREAKER_URL)",
    )

    args = parser.parse_args()

    banner = rf"""
{CYAN}{BOLD}
     _                    _   ____                 _
    / \   __ _  ___ _ __ | |_| __ ) _ __ ___  __ _| | _____ _ __
   / _ \ / _` |/ _ \ '_ \| __|  _ \| '__/ _ \/ _` | |/ / _ \ '__|
  / ___ \ (_| |  __/ | | | |_| |_) | | |  __/ (_| |   <  __/ |
 /_/   \_\__, |\___|_| |_|\__|____/|_|  \___|\__,_|_|\_\___|_|
         |___/
{RESET}{DIM}         Real-time agent safety monitoring{RESET}
"""
    print(banner)
    print(f"  {DIM}Backend  : {args.base_url}{RESET}")
    print(f"  {DIM}API Key  : {args.api_key[:10]}...{RESET}")
    print(f"  {DIM}Scenario : {args.scenario}{RESET}")
    print(f"  {DIM}Mode     : {'offline (mock tools)' if args.offline else 'online'}{RESET}")

    try:
        with AgentBreaker(api_key=args.api_key, base_url=args.base_url) as ab:
            SCENARIOS[args.scenario](ab)
    except AgentBreakerAPIError as exc:
        print_connection_error(exc)
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}Demo interrupted by user.{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
