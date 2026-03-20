"""Ingest service -- the core step processing pipeline."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.detection.engine import DetectionEngine
from app.models.agent import Agent
from app.models.incident import Incident
from app.models.project import Project
from app.models.step import Step
from app.schemas.step import StepCreate
from app.core.input_validation import (
    sanitize_text,
    validate_agent_id,
    validate_step_tokens,
    MAX_INPUT_LENGTH,
    MAX_OUTPUT_LENGTH,
)
from app.services.carbon import calculate_kwh, calculate_co2_grams, infer_model_class

# Singleton detection engine
_engine = DetectionEngine()


async def process_step(
    db: AsyncSession,
    project_id: UUID,
    step_data: StepCreate,
    redis=None,
) -> dict:
    """Process a single agent step through the detection pipeline.

    1. Find or create agent by external_id
    2. Create Step record
    3. Update agent counters
    4. Load last 20 steps
    5. Run detection engine
    6. Update agent risk_score and status
    7. If kill -> create Incident, publish to Redis
    8. If warn -> publish warning to Redis
    9. Return AnalysisResponse dict
    """
    now = datetime.now(timezone.utc)

    # --- Input validation & sanitization ---
    validated_agent_id = validate_agent_id(step_data.agent_id)
    validate_step_tokens(step_data.tokens)
    clean_input = sanitize_text(step_data.input, max_length=MAX_INPUT_LENGTH)
    clean_output = sanitize_text(step_data.output, max_length=MAX_OUTPUT_LENGTH)

    # Load project for thresholds and carbon region
    proj_result = await db.execute(select(Project).where(Project.id == project_id))
    project = proj_result.scalar_one()

    # 1. Find or create agent
    agent = await _find_or_create_agent(db, project_id, validated_agent_id, now)

    # 2. Compute step number
    step_count_result = await db.execute(
        select(func.count(Step.id)).where(Step.agent_id == agent.id)
    )
    current_step_count = step_count_result.scalar() or 0
    step_number = current_step_count + 1

    # Compute carbon for this step
    cost_per_1k = (step_data.cost / max(step_data.tokens, 1)) * 1000 if step_data.tokens > 0 else 0.0
    model_class = infer_model_class(cost_per_1k)
    kwh = calculate_kwh(step_data.tokens, model_class)
    co2 = calculate_co2_grams(kwh, project.carbon_region)

    # Create Step record
    step = Step(
        agent_id=agent.id,
        step_number=step_number,
        input_text=clean_input,
        output_text=clean_output,
        tokens_used=step_data.tokens,
        cost=step_data.cost,
        tool_name=step_data.tool,
        duration_ms=step_data.duration_ms,
        context_size=step_data.context_size,
        error_message=step_data.error_message,
    )
    db.add(step)

    # 3. Update agent counters
    agent.total_cost += step_data.cost
    agent.total_tokens += step_data.tokens
    agent.total_steps = step_number
    agent.total_co2_grams += co2
    agent.total_kwh += kwh
    agent.last_seen_at = now
    agent.status = "running"

    await db.flush()

    # 4. Load last 20 steps for detection analysis
    steps_result = await db.execute(
        select(Step)
        .where(Step.agent_id == agent.id)
        .order_by(Step.step_number.desc())
        .limit(20)
    )
    recent_steps_orm = steps_result.scalars().all()

    # Convert to dicts for the detection engine (chronological order)
    step_dicts = [
        {
            "step_number": s.step_number,
            "input_text": s.input_text,
            "output_text": s.output_text,
            "tokens_used": s.tokens_used,
            "cost": s.cost,
            "tool_name": s.tool_name,
            "duration_ms": s.duration_ms,
            "context_size": s.context_size,
            "error_message": s.error_message,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in reversed(recent_steps_orm)
    ]

    # 5. Run detection engine
    thresholds = project.detection_thresholds or {}
    analysis = await _engine.analyze_step(step_dicts, thresholds)

    risk_score = analysis["score"]
    action = analysis["action"]
    breakdown = analysis["breakdown"]
    warnings = analysis["warnings"]

    # 6. Update agent risk_score and status
    agent.current_risk_score = risk_score
    if action == "kill":
        agent.status = "killed"
    elif action == "warn":
        agent.status = "warning"

    await db.flush()

    # Carbon impact for response
    carbon_impact = {
        "kwh": round(kwh, 6),
        "co2_grams": round(co2, 4),
        "total_kwh": round(agent.total_kwh, 6),
        "total_co2_grams": round(agent.total_co2_grams, 4),
    }

    # 7. If kill -> create Incident with snapshot, publish to Redis
    if action == "kill":
        # Estimate cost avoided (assume agent would have run 2x more steps at current avg cost)
        avg_cost_per_step = agent.total_cost / max(agent.total_steps, 1)
        cost_avoided = avg_cost_per_step * agent.total_steps  # estimate
        avg_tokens_per_step = agent.total_tokens / max(agent.total_steps, 1)
        tokens_avoided = int(avg_tokens_per_step * agent.total_steps)
        kwh_avoided = calculate_kwh(tokens_avoided, model_class)
        co2_avoided = calculate_co2_grams(kwh_avoided, project.carbon_region)

        # Determine incident type from flags
        flags = analysis.get("flags", [])
        incident_type = flags[0] if flags else "composite"

        snapshot = {
            "breakdown": breakdown,
            "warnings": warnings,
            "recent_steps_summary": [
                {"step": s["step_number"], "cost": s["cost"], "tokens": s["tokens_used"]}
                for s in step_dicts[-5:]
            ],
            "agent_totals": {
                "total_cost": agent.total_cost,
                "total_tokens": agent.total_tokens,
                "total_steps": agent.total_steps,
            },
        }

        incident = Incident(
            agent_id=agent.id,
            project_id=project_id,
            incident_type=incident_type,
            risk_score_at_kill=risk_score,
            cost_at_kill=agent.total_cost,
            cost_avoided=round(cost_avoided, 4),
            co2_avoided_grams=round(co2_avoided, 4),
            kwh_avoided=round(kwh_avoided, 6),
            steps_at_kill=agent.total_steps,
            snapshot=snapshot,
            kill_reason_detail="; ".join(warnings) if warnings else "Composite risk threshold exceeded",
        )
        db.add(incident)
        await db.flush()

        # Publish to Redis (graceful if unavailable)
        await _safe_publish(redis, str(project.org_id), {
            "type": "incident",
            "incident_id": str(incident.id),
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "incident_type": incident_type,
            "risk_score": risk_score,
            "cost_avoided": round(cost_avoided, 4),
            "timestamp": now.isoformat(),
        })

    # 8. If warn -> publish warning to Redis
    elif action == "warn":
        await _safe_publish(redis, str(project.org_id), {
            "type": "warning",
            "agent_id": str(agent.id),
            "agent_name": agent.name,
            "risk_score": risk_score,
            "warnings": warnings,
            "timestamp": now.isoformat(),
        })

    # 9. Return AnalysisResponse
    return {
        "step_number": step_number,
        "risk_score": risk_score,
        "risk_breakdown": breakdown,
        "action": action,
        "warnings": warnings,
        "carbon_impact": carbon_impact,
    }


async def _safe_publish(redis, org_id: str, event: dict) -> None:
    """Publish event to Redis, silently fail if Redis is unavailable."""
    if redis is None:
        return
    try:
        await redis.publish(f"events:{org_id}", json.dumps(event))
    except Exception:
        pass  # Redis unavailable — not critical for core functionality


async def _find_or_create_agent(
    db: AsyncSession,
    project_id: UUID,
    external_id: str,
    now: datetime,
) -> Agent:
    """Find an existing agent by external_id, or create a new one."""
    result = await db.execute(
        select(Agent).where(
            Agent.project_id == project_id,
            Agent.external_id == external_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is not None:
        return agent

    agent = Agent(
        project_id=project_id,
        external_id=external_id,
        name=external_id,  # default name from external_id
        status="running",
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(agent)
    await db.flush()
    return agent
