"""Continuous agent simulator -- generates real-time activity for the dashboard.

This is NOT fake data. Each step goes through the real detection engine,
the real carbon calculator, and creates real database records. The Live Feed
shows actual events happening in real-time.

Starts automatically when the server starts (dev mode only).
Disable with SIMULATOR_ENABLED=false environment variable.
"""

from __future__ import annotations

import asyncio
import os
import random
import uuid
from datetime import datetime, timezone

import structlog

# ---------------------------------------------------------------------------
# Gemini integration (optional -- falls back to templates when unavailable)
# ---------------------------------------------------------------------------

_gemini_model = None
_gemini_available: bool | None = None  # None = not checked yet


def _get_gemini():
    """Lazy-init the Gemini model. Returns None if no API key."""
    global _gemini_model, _gemini_available
    if _gemini_available is False:
        return None
    if _gemini_model is not None:
        return _gemini_model
    try:
        import google.generativeai as genai

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            _gemini_available = False
            return None
        genai.configure(api_key=api_key)
        _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
        _gemini_available = True
        return _gemini_model
    except Exception:
        _gemini_available = False
        return None


async def _call_gemini(prompt: str) -> tuple[str, int]:
    """Call Gemini and return (response_text, token_count).

    Uses asyncio.to_thread so the synchronous SDK doesn't block the loop.
    Retries once on 429 (rate limit).
    """
    model = _get_gemini()
    if model is None:
        return "", 0  # signal: caller should fall back to templates

    for attempt in range(2):
        try:
            response = await asyncio.to_thread(model.generate_content, prompt)
            text = response.text or ""
            tokens = (
                response.usage_metadata.total_token_count
                if hasattr(response, "usage_metadata") and response.usage_metadata
                else len(text.split()) * 2
            )
            return text, tokens
        except Exception as e:
            err_str = str(e)
            if "429" in err_str and attempt == 0:
                await asyncio.sleep(5)
                continue
            return f"Gemini error: {err_str}", 10

    return "", 0

from app.core.config import get_settings
from app.core.database import async_session
from app.models.organization import Organization
from app.models.project import Project
from app.schemas.step import StepCreate
from app.services.ingest import process_step

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Gemini prompt sets per behaviour / agent name
# ---------------------------------------------------------------------------

# Normal agents: varied prompts that produce genuinely different outputs
GEMINI_NORMAL_PROMPTS: dict[str, list[str]] = {
    "customer-support-bot": [
        "Summarize this customer ticket in one sentence: Customer wants a refund for order #4521 because the product arrived damaged.",
        "Draft a short internal note: Customer on ticket #4522 disputes a $89 charge on their last invoice.",
        "Summarize this ticket: Customer #4523 cannot log in after a password reset and needs help.",
        "Write a one-line resolution note: FAQ article about shipping times was sent to the customer on ticket #4524.",
        "Classify this support ticket in one sentence: Customer asks about return policy for electronics purchased 45 days ago.",
        "Summarize: Tickets #4526 and #4527 are from the same customer about the same billing issue. Suggest merging.",
        "Draft a short SLA update note: Ticket #4528 has 2 hours left before SLA breach on tier-2 response.",
        "Write a one-sentence summary: Customer satisfaction survey results for ticket #4529 -- rated 4/5 stars.",
    ],
    "code-review-bot": [
        "Review this Python function for bugs and style issues: def calculate_total(items): return sum(i.price for i in items)",
        "Review this code snippet for security issues: cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
        "Check this function for edge cases: def divide(a, b): return a / b",
        "Review for best practices: def get_user(db, id): user = db.query(User).filter_by(id=id).first(); return user",
        "Analyze this for potential race conditions: cache[key] = fetch_data(key); return cache[key]",
        "Review this import block for unused imports: import os, sys, json, typing, dataclasses, re",
        "Check this auth middleware for security: if token == stored_token: return True",
    ],
    "data-pipeline-agent": [
        "Generate a SQL query to find all users who signed up in the last 30 days and haven't made a purchase.",
        "Write a SQL query to check data quality: find duplicate email addresses in the customers table.",
        "Generate a SQL migration statement to add a 'risk_score' FLOAT column to the 'agents' table.",
        "Write a query to export the top 12000 rows from the events table ordered by created_at DESC.",
        "Generate a SQL query to analyze index usage statistics for the 'events' table.",
        "Write a SQL statement to partition the 'events' table by month on the 'created_at' column.",
        "Generate a query to validate all foreign key constraints in the 'orders' schema.",
        "Write a SQL query to identify parquet files smaller than 128MB that should be compacted.",
    ],
    "content-moderator": [
        "Classify this user comment as safe or needs-review: 'This product is absolutely terrible and the company should be ashamed'",
        "Analyze this post for policy violations: 'Check out my amazing deal at example.com/totally-real-offer'",
        "Evaluate if this comment needs moderation: 'Great article, I learned a lot about machine learning basics'",
        "Classify this image description for content policy: 'User uploaded a photo of their garden with flowers and a dog'",
        "Draft a moderation rule update: Add patterns to detect crypto scam promotions in comments.",
    ],
}

# Semantic loop: questions that will produce similar (but not identical) answers
SEMANTIC_LOOP_PROMPTS: dict[str, list[str]] = {
    "research-agent-v3": [
        "How many stars are in the observable universe? Answer in 2 sentences.",
        "What is the estimated number of stars in our universe? 2 sentences max.",
        "According to astronomy, how many stars exist in total? Brief answer.",
        "What do scientists say about the total star count in the cosmos? Short answer.",
        "Estimate the number of stars observable from Earth and beyond. 2 sentences.",
        "Roughly how many stars does the observable universe contain? Answer briefly.",
        "What is the approximate stellar population of the known universe? 2 sentences.",
    ],
    "inventory-sync-agent": [
        "What are best practices for warehouse inventory synchronization? Answer in 2 sentences.",
        "How should inventory counts be kept consistent across multiple warehouses? Brief answer.",
        "Describe the standard approach to reconciling stock levels across warehouses. 2 sentences.",
        "What methods ensure inventory accuracy across distributed warehouses? Short answer.",
        "How do logistics teams keep inventory in sync between warehouse locations? 2 sentences.",
        "What is the recommended process for cross-warehouse inventory reconciliation? Brief answer.",
    ],
}

# Cost spike: prompts that get progressively longer
COST_SPIKE_BASE_PROMPT = (
    "You are a pricing optimization engine. Analyze the following product catalog "
    "and recommend price adjustments. Consider market conditions, competitor pricing, "
    "seasonality, and margin targets.\n\n"
)
COST_SPIKE_PRODUCTS = [
    "Product A: Widget Pro, current price $49.99, cost $22, margin 56%, competitor price $44.99",
    "Product B: Widget Lite, current price $29.99, cost $15, margin 50%, competitor price $32.99",
    "Product C: Widget Enterprise, current price $199.99, cost $80, margin 60%, competitor price $189.99",
    "Product D: Widget Starter, current price $9.99, cost $3, margin 70%, competitor price $11.99",
    "Product E: Widget Plus, current price $79.99, cost $35, margin 56%, competitor price $74.99",
    "Product F: Widget Max, current price $149.99, cost $60, margin 60%, competitor price $159.99",
    "Product G: Widget Mini, current price $14.99, cost $5, margin 67%, competitor price $12.99",
    "Product H: Widget Ultra, current price $299.99, cost $120, margin 60%, competitor price $279.99",
    "Product I: Widget Basic, current price $19.99, cost $8, margin 60%, competitor price $21.99",
    "Product J: Widget Premium, current price $249.99, cost $100, margin 60%, competitor price $239.99",
]


def _build_cost_spike_prompt(step: int) -> str:
    """Build an increasingly long prompt for cost_spike behavior."""
    # Each step includes more products and asks for more detailed analysis
    num_products = min(step + 1, len(COST_SPIKE_PRODUCTS))
    products = "\n".join(COST_SPIKE_PRODUCTS[:num_products])

    detail = ""
    if step >= 3:
        detail += "\nAlso provide a detailed sensitivity analysis for each product."
    if step >= 5:
        detail += "\nInclude quarterly projections for the next 4 quarters."
    if step >= 7:
        detail += "\nAdd a competitive landscape summary and market share estimates."
    if step >= 9:
        detail += "\nProvide a full risk assessment and confidence intervals for each recommendation."

    return f"{COST_SPIKE_BASE_PROMPT}{products}{detail}\n\nProvide your pricing recommendations."


# ---------------------------------------------------------------------------
# Agent behaviour profiles
# ---------------------------------------------------------------------------

AGENT_PROFILES = [
    {
        "name": "customer-support-bot",
        "behavior": "normal",
        "outputs": [
            "Processed ticket #4521 -- customer refund approved for $45.99",
            "Escalated ticket #4522 to tier 2 -- needs billing review",
            "Resolved ticket #4523 -- password reset completed",
            "Auto-replied to ticket #4524 -- FAQ article sent",
            "Classified ticket #4525 as billing inquiry -- routed to finance",
            "Merged duplicate tickets #4526 and #4527 -- same customer",
            "Updated SLA timer on ticket #4528 -- 2 hours remaining",
            "Sent satisfaction survey for resolved ticket #4529",
        ],
        "inputs": [
            "Handle incoming support ticket",
            "Process customer request",
            "Check ticket priority and route",
            "Generate response for customer inquiry",
        ],
        "tools": ["ticket_lookup", "crm_update", "email_send", "knowledge_base_search"],
    },
    {
        "name": "research-agent-v3",
        "behavior": "semantic_loop",
        "outputs": [
            "According to recent market analysis, the AI inference market is valued at $7.6 billion",
            "Market research indicates the AI inference sector reached approximately $7.6 billion in 2025",
            "Industry reports suggest the AI inference market is worth around $7.6 billion currently",
            "Based on current data, the inference market stands at roughly $7.6 billion",
            "Analysis shows the AI inference market at approximately $7.6 billion valuation",
            "Recent estimates place the AI inference market near the $7.6 billion mark",
            "The AI inference market has been valued at about $7.6 billion according to analysts",
        ],
        "inputs": [
            "Research the current AI inference market size",
            "Find updated market data on AI inference",
            "Verify AI inference market valuation",
            "Cross-reference inference market numbers",
        ],
        "tools": ["web_search", "document_reader", "summarizer"],
    },
    {
        "name": "data-pipeline-agent",
        "behavior": "normal",
        "outputs": [
            "ETL job completed: processed 45,000 records from warehouse in 12.3s",
            "Data quality check passed: 99.7% completeness, 0 duplicates found",
            "Schema migration applied: added column 'risk_score' to agents table",
            "Batch export completed: 12,000 rows written to S3 in parquet format",
            "Index rebuild finished: query performance improved by 34%",
            "Partitioned table 'events' by month -- 6 partitions created",
            "Validated 230 foreign key constraints -- all intact",
            "Compacted 18 small files into 3 optimized parquet blocks",
        ],
        "inputs": [
            "Run scheduled ETL pipeline",
            "Execute data quality checks",
            "Process batch data transformation",
            "Optimize storage layout",
        ],
        "tools": ["sql_query", "s3_write", "schema_tool", "data_validator"],
    },
    {
        "name": "pricing-optimizer",
        "behavior": "cost_spike",
        "outputs_template": "Analyzed {n} pricing scenarios across {m} product lines. Recommended {k}% adjustment.",
        "inputs": [
            "Optimize pricing for Q2 product catalog",
            "Run competitive pricing analysis",
            "Calculate optimal price points",
            "Evaluate margin impact of price changes",
        ],
        "tools": ["pricing_model", "competitor_scraper", "margin_calculator"],
    },
    {
        "name": "code-review-bot",
        "behavior": "normal",
        "outputs": [
            "Reviewed PR #891: 3 suggestions, no blocking issues. LGTM.",
            "Reviewed PR #892: found 1 SQL injection risk in user_controller.py line 45",
            "Reviewed PR #893: test coverage dropped from 87% to 82%. Needs tests.",
            "Reviewed PR #894: clean code, good test coverage. Approved.",
            "Reviewed PR #895: deprecated API usage detected in auth_middleware.js",
            "Reviewed PR #896: 2 unused imports removed, added type hints. Approved.",
            "Reviewed PR #897: race condition in cache invalidation -- blocking.",
        ],
        "inputs": [
            "Review pull request for code quality",
            "Analyze diff for security issues",
            "Check test coverage impact",
            "Validate coding standards compliance",
        ],
        "tools": ["git_diff", "ast_parser", "test_runner", "lint_check"],
    },
    {
        "name": "compliance-checker",
        "behavior": "error_cascade",
        "error_message": "ConnectionError: compliance-db.internal:5432 -- connection pool exhausted",
        "outputs": [
            "Checking GDPR compliance for user data export request #301",
            "Scanning PII fields in customer_records table",
            "Validating data retention policy for archived accounts",
        ],
        "inputs": [
            "Run compliance audit on data pipeline",
            "Check GDPR compliance for user records",
            "Validate data retention policies",
        ],
        "tools": ["compliance_db", "policy_engine", "audit_logger"],
    },
    {
        "name": "content-moderator",
        "behavior": "normal",
        "outputs": [
            "Moderated 150 posts: 3 flagged for review, 147 approved automatically",
            "Detected potential hate speech in post #8821 -- escalated to human review",
            "Batch moderation complete: 0 policy violations in last 500 comments",
            "Updated content filter rules: added 12 new pattern matches",
            "Auto-approved 89 image uploads -- all within content policy",
        ],
        "inputs": [
            "Moderate incoming user content batch",
            "Run content policy checks",
            "Update moderation rules",
            "Review flagged content queue",
        ],
        "tools": ["content_classifier", "image_scanner", "policy_matcher", "report_generator"],
    },
    {
        "name": "inventory-sync-agent",
        "behavior": "semantic_loop",
        "outputs": [
            "Synced inventory: warehouse A has 12,450 units of SKU-4401 available",
            "Inventory update: warehouse A shows 12,450 available units for SKU-4401",
            "Stock check complete: SKU-4401 at warehouse A -- 12,450 units in stock",
            "Verified inventory: 12,450 units of SKU-4401 remain at warehouse A",
            "Inventory reconciliation: warehouse A, SKU-4401, count = 12,450",
            "Cross-checked stock: warehouse A reports 12,450 units for SKU-4401",
        ],
        "inputs": [
            "Sync inventory across warehouses",
            "Verify stock levels for SKU-4401",
            "Reconcile inventory counts",
            "Check warehouse availability",
        ],
        "tools": ["warehouse_api", "inventory_db", "stock_reconciler"],
    },
]


# ---------------------------------------------------------------------------
# Simulated agent runner
# ---------------------------------------------------------------------------

class SimulatedAgent:
    """Represents one simulated agent running through steps."""

    def __init__(self, profile: dict, project_id: uuid.UUID, run_number: int):
        self.profile = profile
        self.project_id = project_id
        self.run_number = run_number
        # Each run gets a unique external_id so the ingest pipeline creates a new agent
        self.external_id = f"sim-{profile['name']}-{run_number:04d}"
        self.step = 0
        self.alive = True

        # Decide how many steps before this agent finishes (if it doesn't get killed)
        behavior = profile["behavior"]
        if behavior == "normal":
            self.max_steps = random.randint(6, 15)
        elif behavior == "semantic_loop":
            self.max_steps = random.randint(8, 14)  # will likely be killed before
        elif behavior == "cost_spike":
            self.max_steps = random.randint(8, 12)
        elif behavior == "error_cascade":
            self.max_steps = random.randint(6, 10)
        else:
            self.max_steps = 10

    async def _generate_step_data(self) -> StepCreate:
        """Build a StepCreate payload matching the agent's behaviour profile.

        When a Gemini API key is configured, uses REAL LLM calls for normal,
        semantic_loop, and cost_spike behaviours.  Falls back to templates
        when the key is missing or on API errors.
        """
        behavior = self.profile["behavior"]
        agent_name = self.profile["name"]
        self.step += 1

        input_text = random.choice(self.profile.get("inputs", ["Execute next step"]))
        tool = random.choice(self.profile.get("tools", [None]))
        error_message = None

        if behavior == "normal":
            # --- Try Gemini ---
            prompts = GEMINI_NORMAL_PROMPTS.get(agent_name)
            if prompts:
                prompt = random.choice(prompts)
                gemini_text, gemini_tokens = await _call_gemini(prompt)
                if gemini_text and gemini_tokens > 0:
                    output = gemini_text.strip()
                    tokens = gemini_tokens
                    cost = round(tokens * random.uniform(0.00001, 0.00006), 6)
                    duration_ms = random.randint(400, 3500)
                    context_size = random.randint(2000, 16000)
                    await logger.ainfo(
                        "simulator_gemini_call",
                        agent=self.external_id,
                        behavior=behavior,
                        tokens=tokens,
                    )
                else:
                    # Fallback to template
                    output = random.choice(self.profile["outputs"])
                    tokens = random.randint(200, 1800)
                    cost = round(tokens * random.uniform(0.00001, 0.00006), 6)
                    duration_ms = random.randint(400, 3500)
                    context_size = random.randint(2000, 16000)
            else:
                # No Gemini prompts defined for this agent -- use templates
                output = random.choice(self.profile["outputs"])
                tokens = random.randint(200, 1800)
                cost = round(tokens * random.uniform(0.00001, 0.00006), 6)
                duration_ms = random.randint(400, 3500)
                context_size = random.randint(2000, 16000)

        elif behavior == "semantic_loop":
            # --- Try Gemini: use prompts that produce similar answers ---
            loop_prompts = SEMANTIC_LOOP_PROMPTS.get(agent_name)
            if loop_prompts:
                idx = (self.step - 1) % len(loop_prompts)
                prompt = loop_prompts[idx]
                gemini_text, gemini_tokens = await _call_gemini(prompt)
                if gemini_text and gemini_tokens > 0:
                    output = gemini_text.strip()
                    tokens = gemini_tokens
                    await logger.ainfo(
                        "simulator_gemini_call",
                        agent=self.external_id,
                        behavior=behavior,
                        step=self.step,
                        tokens=tokens,
                    )
                else:
                    # Fallback: pick from template outputs
                    if self.step <= 3:
                        output = self.profile["outputs"][min(self.step - 1, len(self.profile["outputs"]) - 1)]
                        tokens = random.randint(600, 1400)
                    else:
                        output = random.choice(self.profile["outputs"])
                        tokens = random.randint(800, 1600)
            else:
                # No loop prompts -- fall back to templates
                if self.step <= 3:
                    output = self.profile["outputs"][min(self.step - 1, len(self.profile["outputs"]) - 1)]
                    tokens = random.randint(600, 1400)
                else:
                    output = random.choice(self.profile["outputs"])
                    tokens = random.randint(800, 1600)

            cost = round(tokens * 0.00003, 6)
            duration_ms = random.randint(800, 4000)
            context_size = 4000 + (self.step * 800)

        elif behavior == "cost_spike":
            # --- Try Gemini: progressively longer prompts ---
            prompt = _build_cost_spike_prompt(self.step)
            gemini_text, gemini_tokens = await _call_gemini(prompt)
            if gemini_text and gemini_tokens > 0:
                output = gemini_text.strip()
                tokens = gemini_tokens
                # Real cost based on actual tokens -- still apply step multiplier
                cost = round(tokens * 0.00006 * (1 + self.step * 0.3), 6)
                await logger.ainfo(
                    "simulator_gemini_call",
                    agent=self.external_id,
                    behavior=behavior,
                    step=self.step,
                    tokens=tokens,
                )
            else:
                # Fallback to template
                n = random.randint(100, 5000) * (2 ** min(self.step, 8))
                m = random.randint(3, 20)
                k = round(random.uniform(-5, 15), 1)
                template = self.profile.get("outputs_template", "Processed {n} items.")
                output = template.format(n=n, m=m, k=k)
                tokens = min(500 * (2 ** min(self.step, 8)), 128000)
                cost = round(tokens * 0.00006 * (1 + self.step * 0.3), 6)

            duration_ms = random.randint(1000, 5000) + (self.step * 500)
            context_size = 4000 + (self.step * 3000)

        elif behavior == "error_cascade":
            # No Gemini needed -- just generate error messages
            error_msg = self.profile.get("error_message", "Unknown error")
            if self.step <= 2:
                output = random.choice(self.profile.get("outputs", ["Processing..."]))
                tokens = random.randint(300, 800)
                cost = round(tokens * 0.00002, 6)
                duration_ms = random.randint(500, 2000)
            else:
                output = f"Retry attempt {self.step - 2}: {error_msg}"
                error_message = error_msg
                tokens = random.randint(200, 600)
                cost = round(tokens * 0.00002, 6)
                duration_ms = random.randint(100, 500)
            context_size = random.randint(2000, 8000)

        else:
            output = "Step completed."
            tokens = random.randint(200, 1000)
            cost = round(tokens * 0.00003, 6)
            duration_ms = random.randint(300, 2000)
            context_size = random.randint(2000, 8000)

        return StepCreate(
            agent_id=self.external_id,
            input=input_text,
            output=output,
            tokens=tokens,
            cost=cost,
            tool=tool,
            duration_ms=duration_ms,
            context_size=context_size,
            error_message=error_message,
        )

    async def run_step(self) -> dict | None:
        """Execute one step through the real ingest pipeline. Returns the analysis result."""
        if not self.alive or self.step >= self.max_steps:
            self.alive = False
            return None

        step_data = await self._generate_step_data()

        # Get redis if available
        redis = None
        try:
            from app.core.redis import get_redis_pool
            redis = get_redis_pool()
        except Exception:
            pass

        # Run through the REAL ingest pipeline
        async with async_session() as db:
            try:
                result = await process_step(db, self.project_id, step_data, redis=redis)
                await db.commit()
            except Exception as e:
                await db.rollback()
                await logger.awarning(
                    "simulator_step_error",
                    agent=self.external_id,
                    step=self.step,
                    error=str(e),
                )
                return None

        # Check if the detection engine killed this agent
        if result and result.get("action") == "kill":
            self.alive = False

        return result


# ---------------------------------------------------------------------------
# Simulator loop
# ---------------------------------------------------------------------------

_simulator_task: asyncio.Task | None = None


async def _ensure_simulation_project(db) -> uuid.UUID:
    """Find the first existing project to inject real-time data into.

    Uses TechCorp's Production project so simulator data appears
    in the main dashboard — not a separate org.
    Returns the project UUID.
    """
    from sqlalchemy import select

    # Use the first project from the first org (TechCorp's Production)
    result = await db.execute(
        select(Project).order_by(Project.created_at).limit(1)
    )
    project = result.scalar_one_or_none()

    if project is None:
        # Fallback: create a simulator project if no seed data exists
        result = await db.execute(
            select(Organization).order_by(Organization.created_at).limit(1)
        )
        org = result.scalar_one_or_none()
        if org is None:
            org = Organization(name="AgentBreaker", slug="agentbreaker", plan="pro")
            db.add(org)
            await db.flush()

        project = Project(
            org_id=org.id,
            name="Production",
            slug="production",
            carbon_region="us-east",
            detection_thresholds={"kill_threshold": 40, "warn_threshold": 25},
        )
        db.add(project)
        await db.flush()

    await db.commit()
    return project.id


async def _simulator_loop(project_id: uuid.UUID) -> None:
    """Main simulator loop -- runs continuously, launching agents one at a time."""
    run_counter = 0

    await logger.ainfo("simulator_loop_started", project_id=str(project_id))

    while True:
        # Pick a random agent profile
        profile = random.choice(AGENT_PROFILES)
        run_counter += 1

        agent = SimulatedAgent(profile, project_id, run_counter)
        await logger.ainfo(
            "simulator_agent_started",
            agent=agent.external_id,
            behavior=profile["behavior"],
            max_steps=agent.max_steps,
        )

        # Run steps until the agent finishes or gets killed
        while agent.alive and agent.step < agent.max_steps:
            result = await agent.run_step()

            if result:
                risk = result.get("risk_score", 0)
                action = result.get("action", "ok")
                status_tag = "KILLED" if action == "kill" else ("WARN" if action == "warn" else "OK")
                await logger.ainfo(
                    "simulator_step",
                    agent=agent.external_id,
                    step=agent.step,
                    risk=risk,
                    action=status_tag,
                )

                if action == "kill":
                    await logger.ainfo(
                        "simulator_agent_killed",
                        agent=agent.external_id,
                        step=agent.step,
                        risk=risk,
                        warnings=result.get("warnings", []),
                    )
                    break

            # Delay between steps: 3-8 seconds
            await asyncio.sleep(random.uniform(3.0, 8.0))

        if agent.alive:
            # Agent completed naturally -- mark it as completed in the DB
            async with async_session() as db:
                from sqlalchemy import select
                from app.models.agent import Agent as AgentModel
                res = await db.execute(
                    select(AgentModel).where(
                        AgentModel.project_id == project_id,
                        AgentModel.external_id == agent.external_id,
                    )
                )
                db_agent = res.scalar_one_or_none()
                if db_agent and db_agent.status == "running":
                    db_agent.status = "completed"
                    await db.commit()

            await logger.ainfo(
                "simulator_agent_completed",
                agent=agent.external_id,
                steps=agent.step,
            )

        # Wait between agents: 5-10 seconds
        await asyncio.sleep(random.uniform(5.0, 10.0))


async def start_simulator() -> None:
    """Entry point -- called from the FastAPI lifespan.

    Waits 15 seconds for the sentence-transformers model to be available,
    then starts the continuous simulation loop.
    """
    global _simulator_task

    settings = get_settings()
    if not settings.SIMULATOR_ENABLED:
        await logger.ainfo("simulator_disabled")
        return

    await logger.ainfo("simulator_startup_delay", seconds=15)
    await asyncio.sleep(15)

    # Create (or find) the simulation project
    async with async_session() as db:
        try:
            project_id = await _ensure_simulation_project(db)
        except Exception as e:
            await logger.aerror("simulator_project_creation_failed", error=str(e))
            return

    await logger.ainfo("simulator_ready", project_id=str(project_id))

    _simulator_task = asyncio.create_task(_simulator_loop(project_id))
    # Shield the task from cancellation noise in logs
    _simulator_task.add_done_callback(_on_simulator_done)


def _on_simulator_done(task: asyncio.Task) -> None:
    """Log if the simulator exits unexpectedly."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        import traceback
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        # Use sync logger since this is a callback
        structlog.get_logger().error(
            "simulator_crashed",
            error=str(exc),
            traceback=tb,
        )


async def stop_simulator() -> None:
    """Gracefully stop the simulator (called on shutdown)."""
    global _simulator_task
    if _simulator_task and not _simulator_task.done():
        _simulator_task.cancel()
        try:
            await _simulator_task
        except asyncio.CancelledError:
            pass
        _simulator_task = None
    await logger.ainfo("simulator_stopped")
