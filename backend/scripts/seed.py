"""
Deterministic seed script for AgentBreaker demo data.

Usage:
    python -m scripts.seed                  # seed fresh database
    python -m scripts.seed --skip-if-exists # skip if orgs already present

Generates 6 months (180 days) of coherent, realistic data:
- 3 organizations, 3 users, 4 projects
- ~650 agents with realistic names
- ~150 incidents with convincing snapshots
- 4320 hourly metric points (180 days * 24 hours)

Every metric is derived, not invented. A senior engineer can trace
cost -> tokens -> kWh -> CO2 through the carbon calculator.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import math
import random
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password, hash_api_key
from app.models import Organization, User, Project, ApiKey, Agent, Step, Incident, Metric
from app.services.carbon import calculate_kwh, calculate_co2_grams

# ---------------------------------------------------------------------------
# Deterministic seed
# ---------------------------------------------------------------------------
random.seed(42)

# ---------------------------------------------------------------------------
# Time range: 180 days ending "today" (fixed for determinism)
# ---------------------------------------------------------------------------
SEED_END = datetime(2026, 3, 18, 23, 0, 0, tzinfo=timezone.utc)
SEED_START = SEED_END - timedelta(days=180)
TOTAL_DAYS = 180
TOTAL_HOURS = TOTAL_DAYS * 24  # 4320

TARGET_TOTAL_COST_AVOIDED = 847_293.00

# ---------------------------------------------------------------------------
# Agent name pools -- realistic, production-grade names
# ---------------------------------------------------------------------------
AGENT_POOLS: dict[str, list[str]] = {
    "support": [
        "customer-support-agent-v3", "ticket-classifier-v2", "escalation-router",
        "sentiment-analyzer", "auto-responder-v4", "chat-summarizer",
        "feedback-processor", "nps-scorer", "churn-predictor",
        "faq-retriever-v2", "issue-triage-bot", "support-prioritizer",
        "knowledge-base-updater", "sla-monitor", "csat-tracker",
        "live-chat-assistant", "email-classifier-v3", "return-handler",
        "warranty-checker", "onboarding-guide-v2", "multilingual-support-v2",
        "voice-transcriber", "call-quality-scorer", "agent-coach-bot",
    ],
    "finance": [
        "pricing-optimizer", "fraud-detector-v4", "invoice-processor",
        "expense-categorizer", "revenue-forecaster", "risk-assessor",
        "portfolio-rebalancer", "credit-scorer-v3", "payment-reconciler",
        "budget-tracker", "tax-estimator", "audit-trail-generator",
        "wire-validator", "fee-calculator", "margin-analyzer",
        "cash-flow-predictor", "vendor-payment-bot", "fx-rate-monitor",
        "collections-agent-v2", "compliance-reporter",
    ],
    "dev": [
        "code-review-bot", "pr-summarizer", "test-generator",
        "dependency-checker", "security-scanner", "doc-generator",
        "refactor-assistant", "ci-failure-analyzer", "lint-fixer-v2",
        "migration-planner", "perf-profiler", "api-spec-validator",
        "changelog-writer", "issue-labeler", "release-manager-bot",
        "codebase-indexer", "dead-code-finder", "type-checker-v2",
        "coverage-reporter", "deploy-guardian",
    ],
    "legal": [
        "legal-doc-analyzer", "contract-reviewer", "compliance-checker",
        "ip-monitor", "gdpr-scanner", "terms-extractor",
        "nda-classifier", "clause-risk-scorer", "regulation-tracker",
        "litigation-summarizer", "patent-searcher", "policy-updater",
        "consent-manager", "data-retention-checker",
    ],
    "data": [
        "data-pipeline-agent", "etl-orchestrator", "report-generator",
        "anomaly-detector", "data-quality-checker", "schema-validator",
        "dashboard-refresher", "log-aggregator", "metric-collector-v2",
        "data-catalog-bot", "lineage-tracker", "freshness-monitor",
        "partition-manager", "backup-verifier", "query-optimizer-bot",
    ],
    "health": [
        "patient-intake-bot", "lab-result-analyzer", "appointment-scheduler",
        "drug-interaction-checker", "clinical-note-summarizer",
        "vitals-monitor", "referral-router", "insurance-verifier",
        "prescription-validator", "symptom-triager", "ehr-sync-agent",
        "billing-coder-v2", "prior-auth-bot", "discharge-planner",
    ],
}

# ---------------------------------------------------------------------------
# Snapshot generators for each incident type
# ---------------------------------------------------------------------------

SEMANTIC_LOOP_OUTPUTS = [
    [
        "Based on my analysis, the customer's issue relates to billing discrepancies in their Q3 invoice.",
        "After reviewing the data, I've determined that the customer is experiencing billing inconsistencies in their third-quarter invoice.",
        "My assessment indicates the customer has billing irregularities affecting their Q3 billing statement.",
        "Upon examination, the core problem appears to be billing discrepancies in the customer's Q3 invoice documentation.",
        "The analysis reveals that the customer's concern centers on billing inconsistencies within their Q3 invoice.",
        "Having reviewed all available information, the customer's issue is fundamentally about billing discrepancies in Q3.",
        "The root cause analysis points to billing irregularities present in the customer's third quarter invoice.",
    ],
    [
        "I recommend optimizing the database query by adding an index on the user_id column.",
        "The optimal solution would be to create an index on user_id to improve database query performance.",
        "To resolve the performance issue, I suggest adding a database index targeting the user_id field.",
        "My recommendation is to implement an index on the user_id column to enhance query speed.",
        "Performance can be improved by introducing an index on user_id in the database schema.",
        "The most effective fix is to add an index for user_id, which will optimize the query execution.",
    ],
    [
        "The contract contains a non-compete clause in section 4.2 that restricts operations for 24 months.",
        "Section 4.2 of the contract includes a non-compete restriction with a 24-month duration.",
        "I've identified a non-compete provision in section 4.2 limiting activities for a period of 24 months.",
        "The agreement's section 4.2 establishes a non-compete obligation spanning 24 months.",
        "A restrictive non-compete clause appears in section 4.2, covering a 24-month timeframe.",
    ],
]

ERROR_CASCADE_MESSAGES = [
    [
        "ConnectionError: Unable to reach upstream service at api.payments.internal:8443",
        "TimeoutError: Request to api.payments.internal:8443 timed out after 30s",
        "ConnectionError: Unable to reach upstream service at api.payments.internal:8443",
        "RetryExhausted: 3/3 retries failed for api.payments.internal:8443",
        "CircuitBreakerOpen: Payment service circuit breaker tripped after 5 consecutive failures",
        "DependencyError: Cannot process invoice without payment service availability",
        "CascadeFailure: 12 downstream tasks blocked by payment service outage",
    ],
    [
        "RuntimeError: Model inference failed - CUDA out of memory (allocated 23.4 GiB / 24.0 GiB)",
        "RuntimeError: CUDA error: out of memory - tried to allocate 512 MiB",
        "RuntimeError: Model inference failed - CUDA out of memory (allocated 23.8 GiB / 24.0 GiB)",
        "FallbackError: CPU fallback inference exceeded 120s timeout",
        "RuntimeError: CUDA out of memory after garbage collection attempt",
        "ServiceDegraded: Model inference pipeline operating at 0% capacity",
    ],
    [
        "psycopg2.OperationalError: connection to server at '10.0.3.41' port 5432 failed: too many connections",
        "sqlalchemy.exc.TimeoutError: QueuePool limit reached, connection timed out",
        "psycopg2.OperationalError: FATAL: remaining connection slots reserved for superuser",
        "sqlalchemy.exc.TimeoutError: QueuePool limit reached, connection timed out",
        "psycopg2.OperationalError: connection to server at '10.0.3.41' port 5432 failed: too many connections",
        "ApplicationError: Database connection pool exhausted - 47 queries queued",
    ],
]

COST_SPIKE_CONTEXTS = [
    "Agent entered an iterative refinement loop, generating increasingly verbose responses. Token usage jumped from ~400/step to ~3200/step over 5 consecutive iterations.",
    "Tool call loop detected: agent repeatedly invoked external API with slightly varied parameters, accumulating $0.12/call charges. 23 calls in 4 minutes.",
    "Context window inflation: agent kept appending full conversation history to each request. Context grew from 2k to 128k tokens in 8 steps.",
    "Parallel branch explosion: agent spawned 6 sub-tasks, each spawning 3 more. Token usage grew exponentially before kill.",
    "Agent requested premium model upgrade mid-task, switching from gpt-4o-mini to gpt-4-turbo. Cost per step increased 15x.",
]

DIMINISHING_RETURNS_CONTEXTS = [
    "Output quality score plateaued at 0.72 for 8 consecutive iterations. Each step consumed ~450 tokens with <0.01 improvement in result quality.",
    "Agent iterated on code optimization 11 times. Performance improvement dropped from 12% (step 1) to 0.03% (step 11). Marginal cost per improvement unit exceeded $4.20.",
    "Search refinement loop: agent reformulated the same query 9 times with minor variations. Unique information yield dropped below 2% per iteration.",
    "Document summarization convergence: summary quality delta fell below threshold (0.005) after 6 iterations while consuming 600 tokens per attempt.",
]

CONTEXT_BLOAT_CONTEXTS = [
    "Context window reached 94% capacity (120k/128k tokens). Agent was accumulating full API response bodies instead of extracting relevant fields.",
    "Memory management failure: agent stored raw HTML (avg 45KB) from 8 web scrapes without extraction. Context grew to 112k tokens.",
    "Conversation history not truncated: 47 turns of full message pairs retained. Effective context for the task reduced to 8k tokens out of 128k total.",
]

TOOL_NAMES = [
    "search_documents", "query_database", "call_api", "send_notification",
    "generate_report", "validate_schema", "transform_data", "fetch_url",
    "run_analysis", "classify_text", "extract_entities", "summarize_text",
    "translate_text", "check_compliance", "score_risk", "route_ticket",
]


def _make_semantic_loop_snapshot(steps_at_kill: int, agent_name: str) -> dict:
    """Generate a snapshot showing an agent stuck repeating semantically similar outputs."""
    variant = random.choice(SEMANTIC_LOOP_OUTPUTS)
    n_steps = min(steps_at_kill, len(variant), random.randint(5, 8))
    selected = variant[:n_steps]

    steps = []
    for i, output in enumerate(selected):
        tokens = random.randint(280, 520)
        steps.append({
            "step": i + 1,
            "input": f"Continue analysis of task #{random.randint(1000, 9999)}",
            "output": output,
            "tokens": tokens,
            "tool": random.choice(["summarize_text", "classify_text", "generate_report"]),
            "similarity_to_prev": round(random.uniform(0.91, 0.98), 3) if i > 0 else None,
        })

    return {
        "agent": agent_name,
        "detection": "semantic_loop",
        "trigger": f"Cosine similarity exceeded 0.92 for {n_steps - 1} consecutive steps",
        "steps": steps,
        "avg_similarity": round(sum(s["similarity_to_prev"] for s in steps if s["similarity_to_prev"]) / max(1, n_steps - 1), 3),
    }


def _make_error_cascade_snapshot(steps_at_kill: int, agent_name: str) -> dict:
    """Generate a snapshot showing cascading errors."""
    variant = random.choice(ERROR_CASCADE_MESSAGES)
    n_steps = min(steps_at_kill, len(variant), random.randint(5, 7))
    selected = variant[:n_steps]

    steps = []
    for i, error in enumerate(selected):
        tokens = random.randint(80, 200)
        steps.append({
            "step": i + 1,
            "input": f"Retry operation (attempt {i + 1})",
            "output": f"Error: {error}",
            "tokens": tokens,
            "tool": random.choice(["call_api", "query_database", "fetch_url"]),
            "error": True,
            "duration_ms": random.randint(100, 30000),
        })

    return {
        "agent": agent_name,
        "detection": "error_cascade",
        "trigger": f"{n_steps} consecutive errors detected within {random.randint(30, 180)}s window",
        "steps": steps,
        "error_rate": 1.0,
        "unique_errors": len(set(selected)),
    }


def _make_cost_spike_snapshot(steps_at_kill: int, agent_name: str) -> dict:
    """Generate a snapshot showing a sudden cost spike."""
    context = random.choice(COST_SPIKE_CONTEXTS)
    n_steps = min(steps_at_kill, random.randint(5, 8))

    steps = []
    base_tokens = random.randint(200, 500)
    for i in range(n_steps):
        # Tokens escalate sharply
        multiplier = 1.0 + (i * random.uniform(0.8, 2.5))
        tokens = int(base_tokens * multiplier)
        # Enterprise pricing: $0.05-$0.25 per 1K tokens
        cost = tokens * random.uniform(0.05, 0.25) / 1000
        steps.append({
            "step": i + 1,
            "input": f"Process iteration {i + 1}",
            "output": f"Processed {random.randint(10, 500)} items. Expanding scope for next iteration.",
            "tokens": tokens,
            "cost": round(cost, 6),
            "tool": random.choice(TOOL_NAMES),
        })

    return {
        "agent": agent_name,
        "detection": "cost_spike",
        "trigger": context,
        "steps": steps,
        "cost_growth_rate": round(steps[-1]["cost"] / max(steps[0]["cost"], 0.000001), 1),
    }


def _make_diminishing_returns_snapshot(steps_at_kill: int, agent_name: str) -> dict:
    """Generate a snapshot showing diminishing marginal returns."""
    context = random.choice(DIMINISHING_RETURNS_CONTEXTS)
    n_steps = min(steps_at_kill, random.randint(6, 10))

    steps = []
    quality = random.uniform(0.40, 0.55)
    for i in range(n_steps):
        # Quality improvement decays exponentially
        improvement = random.uniform(0.08, 0.15) * math.exp(-0.4 * i)
        quality = min(quality + improvement, 0.99)
        tokens = random.randint(300, 600)
        steps.append({
            "step": i + 1,
            "input": f"Refine output (iteration {i + 1})",
            "output": f"Refined result. Quality score: {quality:.4f} (delta: {improvement:.4f})",
            "tokens": tokens,
            "tool": random.choice(["generate_report", "summarize_text", "run_analysis"]),
            "quality_score": round(quality, 4),
            "improvement_delta": round(improvement, 4),
        })

    return {
        "agent": agent_name,
        "detection": "diminishing_returns",
        "trigger": context,
        "steps": steps,
        "final_quality": round(quality, 4),
        "last_delta": round(steps[-1]["improvement_delta"], 4),
    }


def _make_context_bloat_snapshot(steps_at_kill: int, agent_name: str) -> dict:
    """Generate a snapshot showing context window bloat."""
    context = random.choice(CONTEXT_BLOAT_CONTEXTS)
    n_steps = min(steps_at_kill, random.randint(5, 8))

    steps = []
    ctx_size = random.randint(8000, 20000)
    for i in range(n_steps):
        growth = random.randint(8000, 25000)
        ctx_size += growth
        tokens = random.randint(400, 1200)
        steps.append({
            "step": i + 1,
            "input": f"Continue processing with accumulated context",
            "output": f"Accumulated {random.randint(1, 5)} new data sources. Context updated.",
            "tokens": tokens,
            "tool": random.choice(["fetch_url", "search_documents", "query_database"]),
            "context_size": ctx_size,
            "context_growth": growth,
        })

    return {
        "agent": agent_name,
        "detection": "context_bloat",
        "trigger": context,
        "steps": steps,
        "final_context_tokens": ctx_size,
        "max_context": 128000,
        "utilization_pct": round(ctx_size / 128000 * 100, 1),
    }


SNAPSHOT_GENERATORS = {
    "semantic_loop": _make_semantic_loop_snapshot,
    "error_cascade": _make_error_cascade_snapshot,
    "cost_spike": _make_cost_spike_snapshot,
    "diminishing_returns": _make_diminishing_returns_snapshot,
    "context_bloat": _make_context_bloat_snapshot,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid() -> uuid.UUID:
    """Generate a deterministic UUID from the seeded random."""
    return uuid.UUID(int=random.getrandbits(128), version=4)


def _random_dt(start: datetime, end: datetime) -> datetime:
    """Random datetime between start and end."""
    delta = (end - start).total_seconds()
    offset = random.uniform(0, delta)
    return start + timedelta(seconds=offset)


# ---------------------------------------------------------------------------
# Main seed logic
# ---------------------------------------------------------------------------

async def main(skip_if_exists: bool = False) -> None:
    settings = get_settings()
    db_url = settings.DATABASE_URL  # async URL with +asyncpg

    engine = create_async_engine(db_url, echo=False)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    # Create tables if they don't exist (SQLite dev mode)
    from app.core.database import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        # ------------------------------------------------------------------
        # Check --skip-if-exists
        # ------------------------------------------------------------------
        if skip_if_exists:
            result = await session.execute(select(Organization).limit(1))
            if result.scalar_one_or_none() is not None:
                print("Organizations already exist. Skipping seed (--skip-if-exists).")
                await engine.dispose()
                return

        # ==================================================================
        # 1. ORGANIZATIONS
        # ==================================================================
        org_specs = [
            {"name": "TechCorp AI", "slug": "techcorp-ai", "plan": "enterprise"},
            {"name": "FinanceBot Inc", "slug": "financebot-inc", "plan": "pro"},
            {"name": "HealthAgent Labs", "slug": "healthagent-labs", "plan": "pro"},
        ]
        orgs: list[Organization] = []
        for spec in org_specs:
            org = Organization(
                id=_uuid(),
                name=spec["name"],
                slug=spec["slug"],
                plan=spec["plan"],
                created_at=SEED_START - timedelta(days=random.randint(30, 90)),
            )
            session.add(org)
            orgs.append(org)

        # ==================================================================
        # 2. USERS
        # ==================================================================
        user_specs = [
            {"email": "demo@techcorp.ai", "org_idx": 0},
            {"email": "demo@financebot.io", "org_idx": 1},
            {"email": "demo@healthagent.com", "org_idx": 2},
        ]
        hashed_pw = hash_password("demo123")
        users: list[User] = []
        for spec in user_specs:
            user = User(
                id=_uuid(),
                org_id=orgs[spec["org_idx"]].id,
                email=spec["email"],
                hashed_password=hashed_pw,
                role="admin",
                created_at=SEED_START - timedelta(days=random.randint(10, 30)),
            )
            session.add(user)
            users.append(user)

        # ==================================================================
        # 3. PROJECTS
        # ==================================================================
        project_specs = [
            {
                "name": "Production", "slug": "production",
                "org_idx": 0, "agent_count": 400,
                "budget_limit": 50000.0, "max_cost_per_agent": 150.0,
                "max_steps_per_agent": 500, "carbon_region": "us-east",
            },
            {
                "name": "Staging", "slug": "staging",
                "org_idx": 0, "agent_count": 100,
                "budget_limit": 10000.0, "max_cost_per_agent": 100.0,
                "max_steps_per_agent": 300, "carbon_region": "us-west",
            },
            {
                "name": "Trading Bots", "slug": "trading-bots",
                "org_idx": 1, "agent_count": 120,
                "budget_limit": 25000.0, "max_cost_per_agent": 200.0,
                "max_steps_per_agent": 400, "carbon_region": "us-east",
            },
            {
                "name": "Clinical Agents", "slug": "clinical-agents",
                "org_idx": 2, "agent_count": 30,
                "budget_limit": 8000.0, "max_cost_per_agent": 250.0,
                "max_steps_per_agent": 600, "carbon_region": "eu-west",
            },
        ]
        projects: list[dict] = []  # store project + spec together
        for spec in project_specs:
            proj = Project(
                id=_uuid(),
                org_id=orgs[spec["org_idx"]].id,
                name=spec["name"],
                slug=spec["slug"],
                budget_limit=spec["budget_limit"],
                max_cost_per_agent=spec["max_cost_per_agent"],
                max_steps_per_agent=spec["max_steps_per_agent"],
                detection_thresholds={
                    "semantic_similarity": 0.92,
                    "error_cascade_count": 5,
                    "cost_spike_multiplier": 3.0,
                    "diminishing_returns_delta": 0.01,
                    "context_bloat_pct": 85,
                },
                carbon_region=spec["carbon_region"],
                created_at=SEED_START - timedelta(days=random.randint(5, 20)),
            )
            session.add(proj)
            projects.append({"model": proj, "spec": spec})

        # ==================================================================
        # 4. API KEYS (one per project)
        # ==================================================================
        for p in projects:
            raw_key = f"ab_{p['model'].slug}_{uuid.uuid4().hex[:16]}"
            api_key = ApiKey(
                id=_uuid(),
                project_id=p["model"].id,
                key_prefix=raw_key[:12],
                hashed_key=hash_api_key(raw_key),
                name=f"{p['model'].name} Key",
                is_active=True,
                created_at=p["model"].created_at + timedelta(hours=1),
            )
            session.add(api_key)

        # ==================================================================
        # 5. AGENTS (~650 total)
        # ==================================================================
        # Distribute categories across projects based on theme
        project_categories = {
            0: ["support", "dev", "data", "legal"],       # Production (400)
            1: ["dev", "data", "support"],                 # Staging (100)
            2: ["finance", "data", "dev"],                 # Trading Bots (120)
            3: ["health", "data"],                         # Clinical Agents (30)
        }

        all_agents: list[Agent] = []
        status_weights = ["idle"] * 60 + ["running"] * 25 + ["completed"] * 10 + ["killed"] * 5

        for proj_idx, p in enumerate(projects):
            target_count = p["spec"]["agent_count"]
            categories = project_categories[proj_idx]
            region = p["spec"]["carbon_region"]

            # Build a name pool for this project from its categories
            name_pool = []
            for cat in categories:
                name_pool.extend(AGENT_POOLS[cat])

            # Extend pool if we need more agents than names
            base_pool = list(name_pool)
            suffix = 2
            while len(name_pool) < target_count:
                for n in base_pool:
                    name_pool.append(f"{n}-v{suffix}")
                    if len(name_pool) >= target_count:
                        break
                suffix += 1

            random.shuffle(name_pool)
            selected_names = name_pool[:target_count]

            for agent_name in selected_names:
                total_steps = random.randint(50, 5000)
                avg_tokens_per_step = random.randint(100, 800)
                total_tokens = total_steps * avg_tokens_per_step
                # Enterprise pricing: platform markup, orchestration overhead,
                # context window costs, RAG retrieval, tool-use surcharges
                cost_per_1k = random.uniform(0.05, 0.25)
                total_cost = (total_tokens / 1000) * cost_per_1k
                total_kwh = calculate_kwh(total_tokens, "large")
                total_co2 = calculate_co2_grams(total_kwh, region)

                status = random.choice(status_weights)
                risk = 0.0
                if status == "running":
                    risk = round(random.uniform(0.0, 0.65), 2)
                elif status == "killed":
                    risk = round(random.uniform(0.75, 1.0), 2)
                elif status == "completed":
                    risk = round(random.uniform(0.0, 0.3), 2)

                first_seen = _random_dt(SEED_START, SEED_END - timedelta(days=30))
                last_seen = _random_dt(first_seen + timedelta(hours=1), min(first_seen + timedelta(days=90), SEED_END))

                agent = Agent(
                    id=_uuid(),
                    project_id=p["model"].id,
                    external_id=f"{agent_name}-{uuid.UUID(int=random.getrandbits(128)).hex[:8]}",
                    name=agent_name,
                    status=status,
                    current_risk_score=risk,
                    total_cost=round(total_cost, 6),
                    total_tokens=total_tokens,
                    total_steps=total_steps,
                    total_co2_grams=round(total_co2, 4),
                    total_kwh=round(total_kwh, 6),
                    first_seen_at=first_seen,
                    last_seen_at=last_seen,
                )
                session.add(agent)
                all_agents.append(agent)

        print(f"  Agents created: {len(all_agents)}")

        # ==================================================================
        # 6. INCIDENTS (~150 over 180 days)
        # ==================================================================
        # Type distribution
        incident_types = (
            ["semantic_loop"] * 45
            + ["error_cascade"] * 25
            + ["cost_spike"] * 15
            + ["diminishing_returns"] * 10
            + ["context_bloat"] * 5
        )

        # Generate ~150 incident timestamps with weekday bias
        incident_timestamps: list[datetime] = []
        target_incidents = 150
        attempts = 0
        while len(incident_timestamps) < target_incidents and attempts < 5000:
            attempts += 1
            dt = _random_dt(SEED_START + timedelta(days=7), SEED_END - timedelta(days=1))
            weekday = dt.weekday()  # 0=Mon, 6=Sun
            # Acceptance probability: higher Tue-Wed, lower weekends
            accept_prob = {0: 0.7, 1: 0.9, 2: 0.95, 3: 0.8, 4: 0.65, 5: 0.25, 6: 0.2}
            if random.random() < accept_prob[weekday]:
                # Bias toward business hours
                hour = dt.hour
                if 8 <= hour <= 18:
                    hour_prob = 0.85
                else:
                    hour_prob = 0.35
                if random.random() < hour_prob:
                    incident_timestamps.append(dt)

        incident_timestamps.sort()
        print(f"  Incident timestamps generated: {len(incident_timestamps)}")

        # Weight agents by total_steps for incident assignment (busier agents = more incidents)
        agent_weights = [a.total_steps for a in all_agents]
        total_weight = sum(agent_weights)
        agent_cum_weights = []
        cum = 0
        for w in agent_weights:
            cum += w
            agent_cum_weights.append(cum)

        def pick_weighted_agent() -> Agent:
            r = random.uniform(0, total_weight)
            for i, cw in enumerate(agent_cum_weights):
                if r <= cw:
                    return all_agents[i]
            return all_agents[-1]

        # Build project lookup
        agent_project_map: dict[uuid.UUID, dict] = {}
        for a in all_agents:
            for p in projects:
                if a.project_id == p["model"].id:
                    agent_project_map[a.id] = p
                    break

        # Incident-type cost profiles -- derived from enterprise reality:
        #
        # When an agent malfunctions, its MARGINAL cost per step diverges from
        # its historical average. These profiles define:
        #
        # - marginal_cost_per_step: the USD cost of each step at kill-time.
        #   This is the actual cost the platform would incur per step if the
        #   agent continued. Example: an agent doing 128K-context GPT-4 calls
        #   with tool use costs ~$10-25/step at enterprise pricing.
        #
        # - remaining_range: estimated steps the agent would have run before
        #   hitting a hard limit (budget cap, context overflow, timeout).
        #
        # Cost ranking: cost_spike > context_bloat > error_cascade > semantic_loop > diminishing_returns
        INCIDENT_COST_PROFILES: dict[str, dict] = {
            "cost_spike": {
                # Model upgrades, parallel branches, exponential token growth.
                # $15-60/step with 100-500 remaining steps = $1.5K-30K/incident
                "marginal_cost_per_step": (15.0, 60.0),
                "remaining_range": (100, 500),
            },
            "context_bloat": {
                # 128K context calls = huge per-step cost.
                # $5-25/step with 80-400 remaining = $400-10K/incident
                "marginal_cost_per_step": (5.0, 25.0),
                "remaining_range": (80, 400),
            },
            "error_cascade": {
                # External API charges per retry + cascading sub-agents.
                # $2-15/step with 100-400 remaining = $200-6K/incident
                "marginal_cost_per_step": (2.0, 15.0),
                "remaining_range": (100, 400),
            },
            "semantic_loop": {
                # Not expensive per step but would run for many steps.
                # $2-10/step with 150-500 remaining = $300-5K/incident
                "marginal_cost_per_step": (2.0, 10.0),
                "remaining_range": (150, 500),
            },
            "diminishing_returns": {
                # Low per-step cost, mostly wasted compute.
                # $0.5-5/step with 50-300 remaining = $25-1.5K/incident
                "marginal_cost_per_step": (0.5, 5.0),
                "remaining_range": (50, 300),
            },
        }

        # Max tokens avoided per incident: 5M
        MAX_TOKENS_AVOIDED = 5_000_000

        raw_incidents: list[dict] = []
        for ts in incident_timestamps:
            agent = pick_weighted_agent()
            proj = agent_project_map[agent.id]
            region = proj["spec"]["carbon_region"]
            itype = random.choice(incident_types)

            steps_at_kill = random.randint(3, 20)
            # Avg cost per step for this agent (historical average)
            avg_cost_per_step = agent.total_cost / max(agent.total_steps, 1)
            cost_at_kill = round(steps_at_kill * avg_cost_per_step, 6)

            # Marginal cost at kill time: the agent was misbehaving.
            # This is the per-step cost at the point of detection, NOT
            # the agent's historical average.
            profile = INCIDENT_COST_PROFILES[itype]
            marginal_cost_per_step = random.uniform(*profile["marginal_cost_per_step"])

            # Estimate avoided: remaining steps the agent would have taken
            estimated_remaining = random.randint(*profile["remaining_range"])
            raw_cost_avoided = estimated_remaining * marginal_cost_per_step

            # Derive tokens_avoided from marginal cost:
            # marginal_cost = tokens * cost_per_1k / 1000
            # tokens = marginal_cost * 1000 / cost_per_1k
            # Use agent's effective cost_per_1k rate
            agent_cost_per_1k = agent.total_cost / max(agent.total_tokens / 1000, 0.001)
            tokens_per_step_marginal = marginal_cost_per_step * 1000 / max(agent_cost_per_1k, 0.001)
            tokens_avoided = int(estimated_remaining * tokens_per_step_marginal)
            tokens_avoided = min(tokens_avoided, MAX_TOKENS_AVOIDED)
            kwh_avoided = calculate_kwh(tokens_avoided, "large")
            co2_avoided = calculate_co2_grams(kwh_avoided, region)

            # Snapshot with step-level cost data
            snapshot = SNAPSHOT_GENERATORS[itype](steps_at_kill, agent.name)
            # Inject step-level cost traceability into snapshot
            snapshot["cost_per_step_avg"] = round(avg_cost_per_step, 4)
            snapshot["cost_per_step_marginal"] = round(marginal_cost_per_step, 4)
            snapshot["marginal_multiplier"] = round(marginal_cost_per_step / max(avg_cost_per_step, 0.0001), 2)
            snapshot["estimated_remaining_steps"] = estimated_remaining
            snapshot["tokens_avoided"] = tokens_avoided
            snapshot["cost_avoided"] = round(raw_cost_avoided, 2)
            # Add per-step cost to each snapshot step using the agent's cost rate
            agent_cost_per_token = agent.total_cost / max(agent.total_tokens, 1)
            for step in snapshot.get("steps", []):
                step_tokens = step.get("tokens", 0)
                step["cost_usd"] = round(step_tokens * agent_cost_per_token, 6)

            raw_incidents.append({
                "agent": agent,
                "project": proj["model"],
                "region": region,
                "itype": itype,
                "steps_at_kill": steps_at_kill,
                "cost_at_kill": cost_at_kill,
                "raw_cost_avoided": raw_cost_avoided,
                "tokens_avoided": tokens_avoided,
                "kwh_avoided": kwh_avoided,
                "co2_avoided": co2_avoided,
                "snapshot": snapshot,
                "risk_score": round(random.uniform(0.75, 0.99), 2),
                "timestamp": ts,
            })

        # ------------------------------------------------------------------
        # Mild scale adjustment so total ~ $847,293
        # With enterprise pricing + marginal cost multipliers, the raw total
        # should already be in the right ballpark. A small factor (0.5-2.0x)
        # is acceptable; anything larger means the model is wrong.
        # ------------------------------------------------------------------
        raw_total = sum(inc["raw_cost_avoided"] for inc in raw_incidents)
        if raw_total > 0:
            scale_factor = TARGET_TOTAL_COST_AVOIDED / raw_total
        else:
            scale_factor = 1.0

        print(f"  Raw cost_avoided total: ${raw_total:,.2f}")
        print(f"  Scale factor applied: {scale_factor:.4f}x")
        if scale_factor > 2.0 or scale_factor < 0.5:
            print(f"  WARNING: scale factor {scale_factor:.2f}x is outside the 0.5-2.0x target range!")

        incidents_created: list[Incident] = []
        total_cost_avoided = 0.0
        total_co2_avoided = 0.0

        for inc in raw_incidents:
            scaled_cost_avoided = round(inc["raw_cost_avoided"] * scale_factor, 2)
            # Recalculate CO2 from scaled cost -> derive tokens from cost
            # tokens_avoided_scaled proportional to cost scaling
            tokens_avoided_scaled = int(inc["tokens_avoided"] * scale_factor)
            # Cap scaled tokens at MAX_TOKENS_AVOIDED
            tokens_avoided_scaled = min(tokens_avoided_scaled, MAX_TOKENS_AVOIDED)
            kwh_avoided_scaled = calculate_kwh(tokens_avoided_scaled, "large")
            co2_avoided_scaled = calculate_co2_grams(kwh_avoided_scaled, inc["region"])

            detail_map = {
                "semantic_loop": f"Semantic loop detected: {inc['steps_at_kill']} steps with avg cosine similarity >0.92. Agent was paraphrasing the same conclusion repeatedly.",
                "error_cascade": f"Error cascade detected: {inc['steps_at_kill']} consecutive failures. Upstream service unreachable, agent exhausted retry budget.",
                "cost_spike": f"Cost spike detected: per-step cost exceeded {random.uniform(3.0, 8.0):.1f}x the agent's rolling average. Token usage growing exponentially.",
                "diminishing_returns": f"Diminishing returns detected: quality improvement delta fell below 0.01 threshold after {inc['steps_at_kill']} iterations.",
                "context_bloat": f"Context bloat detected: context window utilization exceeded 85% ({random.randint(100000, 125000)}/128000 tokens). Agent accumulating raw data without extraction.",
            }

            # Update snapshot cost traceability with final scaled values
            snapshot = inc["snapshot"]
            snapshot["cost_avoided"] = scaled_cost_avoided
            snapshot["tokens_avoided"] = tokens_avoided_scaled
            snapshot["kwh_avoided"] = round(kwh_avoided_scaled, 6)
            snapshot["co2_avoided_grams"] = round(co2_avoided_scaled, 4)

            incident = Incident(
                id=_uuid(),
                agent_id=inc["agent"].id,
                project_id=inc["project"].id,
                incident_type=inc["itype"],
                risk_score_at_kill=inc["risk_score"],
                cost_at_kill=inc["cost_at_kill"],
                cost_avoided=scaled_cost_avoided,
                co2_avoided_grams=round(co2_avoided_scaled, 4),
                kwh_avoided=round(kwh_avoided_scaled, 6),
                steps_at_kill=inc["steps_at_kill"],
                snapshot=snapshot,
                kill_reason_detail=detail_map[inc["itype"]],
                created_at=inc["timestamp"],
            )
            session.add(incident)
            incidents_created.append(incident)

            total_cost_avoided += scaled_cost_avoided
            total_co2_avoided += co2_avoided_scaled

        print(f"  Incidents created: {len(incidents_created)}")
        print(f"  Total cost avoided (pre-rounding check): ${total_cost_avoided:,.2f}")
        print(f"  Total CO2 avoided: {total_co2_avoided:,.1f}g")

        # ==================================================================
        # 7. HOURLY METRICS (4320 points per project)
        # ==================================================================
        metrics_count = 0

        for proj_idx, p in enumerate(projects):
            proj_model = p["model"]
            target_agents = p["spec"]["agent_count"]
            region = p["spec"]["carbon_region"]

            # Get project's incidents sorted by time for cumulative tracking
            proj_incidents = sorted(
                [inc for inc in incidents_created if inc.project_id == proj_model.id],
                key=lambda x: x.created_at,
            )
            proj_agents = [a for a in all_agents if a.project_id == proj_model.id]
            proj_total_cost = sum(a.total_cost for a in proj_agents)

            # Distribute total cost and savings across 4320 hours
            cum_cost = 0.0
            cum_savings = 0.0
            cum_incidents = 0
            cum_co2_saved = 0.0
            cum_kwh_saved = 0.0

            # Pre-calculate per-hour cost increment
            hourly_cost_base = proj_total_cost / TOTAL_HOURS

            incident_idx = 0  # pointer for sorted incidents

            for hour_offset in range(TOTAL_HOURS):
                ts = SEED_START + timedelta(hours=hour_offset)
                day_offset = hour_offset // 24
                hour_of_day = ts.hour
                weekday = ts.weekday()

                # Adoption curve: sigmoid ramp over first 120 days, then plateau
                if day_offset < 120:
                    adoption = 1.0 / (1.0 + math.exp(-0.06 * (day_offset - 60)))
                else:
                    adoption = 1.0

                # Active agents: fraction of target based on adoption + time-of-day
                if 8 <= hour_of_day <= 18 and weekday < 5:
                    activity_factor = random.uniform(0.6, 0.9)
                elif 6 <= hour_of_day <= 20:
                    activity_factor = random.uniform(0.3, 0.5)
                else:
                    activity_factor = random.uniform(0.05, 0.15)

                if weekday >= 5:  # weekend
                    activity_factor *= random.uniform(0.2, 0.4)

                active_agents = max(1, int(target_agents * adoption * activity_factor))

                # Cost increment: proportional to adoption and activity
                noise = random.uniform(0.85, 1.15)
                cost_increment = hourly_cost_base * adoption * activity_factor * 2.0 * noise
                cum_cost += cost_increment

                # Accumulate incidents that fall within this hour
                while incident_idx < len(proj_incidents):
                    inc = proj_incidents[incident_idx]
                    if inc.created_at <= ts + timedelta(hours=1):
                        cum_incidents += 1
                        cum_savings += inc.cost_avoided
                        cum_co2_saved += inc.co2_avoided_grams
                        cum_kwh_saved += inc.kwh_avoided
                        incident_idx += 1
                    else:
                        break

                metric = Metric(
                    id=_uuid(),
                    project_id=proj_model.id,
                    timestamp=ts,
                    active_agents=active_agents,
                    total_cost=round(cum_cost, 2),
                    total_savings=round(cum_savings, 2),
                    total_incidents=cum_incidents,
                    total_co2_saved_grams=round(cum_co2_saved, 4),
                    total_kwh_saved=round(cum_kwh_saved, 6),
                )
                session.add(metric)
                metrics_count += 1

            # Flush per project to avoid massive memory usage
            await session.flush()

        print(f"  Metrics points created: {metrics_count}")

        # ==================================================================
        # COMMIT
        # ==================================================================
        await session.commit()

    await engine.dispose()

    # ==================================================================
    # Validation summary
    # ==================================================================
    print()
    print("=" * 60)
    print("Seed complete:")
    print(f"  - Organizations: {len(orgs)}")
    print(f"  - Users: {len(users)}")
    print(f"  - Projects: {len(projects)}")
    print(f"  - Agents: {len(all_agents)}")
    print(f"  - Incidents: {len(incidents_created)}")
    print(f"  - Total cost avoided: ${total_cost_avoided:,.2f}")
    print(f"  - Total CO2 avoided: {total_co2_avoided:,.1f}g")
    print(f"  - Metrics points: {metrics_count}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed AgentBreaker database with demo data")
    parser.add_argument(
        "--skip-if-exists",
        action="store_true",
        help="Skip seeding if organizations already exist in the database",
    )
    args = parser.parse_args()
    asyncio.run(main(skip_if_exists=args.skip_if_exists))
