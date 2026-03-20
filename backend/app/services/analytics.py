"""Analytics service -- query functions for dashboard KPIs and charts."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy import select, func, and_, case, extract, cast, Date, String
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.incident import Incident
from app.models.project import Project
from app.models.step import Step


async def get_overview(db: AsyncSession, org_id: UUID) -> dict:
    """Return KPI overview: total_savings, active_agents, incidents_today, avg_risk_score."""
    project_ids_q = select(Project.id).where(Project.org_id == org_id)

    # Total savings (sum of cost_avoided from incidents)
    savings_result = await db.execute(
        select(func.coalesce(func.sum(Incident.cost_avoided), 0.0))
        .where(Incident.project_id.in_(project_ids_q))
    )
    total_savings = savings_result.scalar() or 0.0

    # Active agents (status = 'running' or 'warning')
    active_result = await db.execute(
        select(func.count(Agent.id))
        .where(
            Agent.project_id.in_(project_ids_q),
            Agent.status.in_(["running", "warning"]),
        )
    )
    active_agents = active_result.scalar() or 0

    # Incidents today
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    incidents_today_result = await db.execute(
        select(func.count(Incident.id))
        .where(
            Incident.project_id.in_(project_ids_q),
            Incident.created_at >= today_start,
        )
    )
    incidents_today = incidents_today_result.scalar() or 0

    # Average risk score across all agents
    avg_result = await db.execute(
        select(func.coalesce(func.avg(Agent.current_risk_score), 0.0))
        .where(Agent.project_id.in_(project_ids_q))
    )
    avg_risk_score = round(avg_result.scalar() or 0.0, 2)

    return {
        "total_savings": round(total_savings, 2),
        "active_agents": active_agents,
        "incidents_today": incidents_today,
        "avg_risk_score": avg_risk_score,
    }


async def get_savings_timeline(
    db: AsyncSession, org_id: UUID, days: int = 30
) -> list[dict]:
    """Return daily cost_saved for the last N days."""
    project_ids_q = select(Project.id).where(Project.org_id == org_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    result = await db.execute(
        select(
            func.substr(func.cast(Incident.created_at, String), 1, 10).label("day"),
            func.coalesce(func.sum(Incident.cost_avoided), 0.0).label("cost_saved"),
        )
        .where(
            Incident.project_id.in_(project_ids_q),
            Incident.created_at >= since,
        )
        .group_by(func.substr(func.cast(Incident.created_at, String), 1, 10))
        .order_by(func.substr(func.cast(Incident.created_at, String), 1, 10))
    )

    rows = result.all()

    # Fill in missing days with 0
    timeline: list[dict] = []
    existing = {str(row[0]): float(row[1]) for row in rows}
    current = since.date()
    end = datetime.now(timezone.utc).date()
    while current <= end:
        date_str = str(current)
        timeline.append({
            "date": date_str,
            "cost_saved": round(existing.get(date_str, 0.0), 4),
        })
        current += timedelta(days=1)

    return timeline


async def get_top_agents(db: AsyncSession, org_id: UUID, limit: int = 10) -> list[dict]:
    """Return top N costliest agents."""
    project_ids_q = select(Project.id).where(Project.org_id == org_id)

    result = await db.execute(
        select(Agent.name, Agent.total_cost)
        .where(Agent.project_id.in_(project_ids_q))
        .order_by(Agent.total_cost.desc())
        .limit(limit)
    )

    return [
        {"agent_name": row[0], "total_cost": round(row[1], 4)}
        for row in result
    ]


async def get_incident_distribution(db: AsyncSession, org_id: UUID) -> list[dict]:
    """Return incident count by type with percentages."""
    project_ids_q = select(Project.id).where(Project.org_id == org_id)

    result = await db.execute(
        select(
            Incident.incident_type,
            func.count(Incident.id).label("count"),
        )
        .where(Incident.project_id.in_(project_ids_q))
        .group_by(Incident.incident_type)
    )

    rows = result.all()
    total = sum(row[1] for row in rows) or 1

    return [
        {
            "type": row[0],
            "count": row[1],
            "percentage": round(row[1] / total * 100, 2),
        }
        for row in rows
    ]


async def get_carbon_report(db: AsyncSession, org_id: UUID) -> dict:
    """Return carbon report: total kWh, CO2, equivalences, monthly trend."""
    from app.services.carbon import calculate_equivalences

    project_ids_q = select(Project.id).where(Project.org_id == org_id)

    # Total kWh and CO2 saved from incidents
    totals = await db.execute(
        select(
            func.coalesce(func.sum(Incident.kwh_avoided), 0.0),
            func.coalesce(func.sum(Incident.co2_avoided_grams), 0.0),
        )
        .where(Incident.project_id.in_(project_ids_q))
    )
    row = totals.one()
    total_kwh_saved = float(row[0])
    total_co2_saved_grams = float(row[1])

    equivalences_raw = calculate_equivalences(total_co2_saved_grams)
    equivalences = {
        "kwh": round(total_kwh_saved, 4),
        "co2_grams": round(total_co2_saved_grams, 4),
        "equivalent_trees": round(equivalences_raw["equivalent_trees"], 4),
        "equivalent_km_car": round(equivalences_raw["equivalent_km_car"], 4),
        "equivalent_phone_charges": round(equivalences_raw["equivalent_phone_charges"], 4),
    }

    # Monthly trend (last 6 months)
    six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
    monthly_result = await db.execute(
        select(
            extract("year", Incident.created_at).label("yr"),
            extract("month", Incident.created_at).label("mn"),
            func.coalesce(func.sum(Incident.kwh_avoided), 0.0),
            func.coalesce(func.sum(Incident.co2_avoided_grams), 0.0),
        )
        .where(
            Incident.project_id.in_(project_ids_q),
            Incident.created_at >= six_months_ago,
        )
        .group_by(
            extract("year", Incident.created_at),
            extract("month", Incident.created_at),
        )
        .order_by(
            extract("year", Incident.created_at),
            extract("month", Incident.created_at),
        )
    )

    monthly_trend = [
        {
            "month": f"{int(r[0])}-{int(r[1]):02d}",
            "kwh_saved": round(float(r[2]), 4),
            "co2_saved_grams": round(float(r[3]), 4),
        }
        for r in monthly_result
    ]

    return {
        "total_kwh_saved": round(total_kwh_saved, 4),
        "total_co2_saved_kg": round(total_co2_saved_grams / 1000, 4),
        "equivalences": equivalences,
        "monthly_trend": monthly_trend,
    }


async def get_heatmap(db: AsyncSession, org_id: UUID) -> dict:
    """Return 7x24 activity heatmap (day_of_week x hour_of_day) from steps."""
    project_ids_q = select(Project.id).where(Project.org_id == org_id)
    agent_ids_q = select(Agent.id).where(Agent.project_id.in_(project_ids_q))

    # Query step counts grouped by day of week and hour
    result = await db.execute(
        select(
            extract("dow", Step.created_at).label("dow"),   # 0=Sunday in PG
            extract("hour", Step.created_at).label("hour"),
            func.count(Step.id),
        )
        .where(Step.agent_id.in_(agent_ids_q))
        .group_by(
            extract("dow", Step.created_at),
            extract("hour", Step.created_at),
        )
    )

    # Build 7x24 matrix (rows = days, cols = hours)
    matrix = [[0] * 24 for _ in range(7)]
    for row in result:
        dow = int(row[0])  # 0=Sunday
        hour = int(row[1])
        count = int(row[2])
        matrix[dow][hour] = count

    labels_y = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    labels_x = [f"{h:02d}:00" for h in range(24)]

    return {
        "data": matrix,
        "labels_x": labels_x,
        "labels_y": labels_y,
    }
