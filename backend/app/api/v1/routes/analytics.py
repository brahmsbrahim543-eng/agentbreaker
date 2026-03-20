"""Analytics routes -- dashboard KPIs, charts, and carbon reporting."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_org
from app.schemas.analytics import (
    OverviewResponse,
    SavingsTimelinePoint,
    TopAgentEntry,
    IncidentDistribution,
    HeatmapResponse,
)
from app.schemas.carbon import CarbonReport, CarbonImpact
from app.services.analytics import (
    get_overview,
    get_savings_timeline,
    get_top_agents,
    get_incident_distribution,
    get_carbon_report,
    get_heatmap,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """KPI overview: total savings, active agents, incidents today, avg risk score."""
    data = await get_overview(db, org_id)
    return OverviewResponse(**data)


@router.get("/savings-timeline", response_model=list[SavingsTimelinePoint])
async def savings_timeline(
    days: int = Query(30, ge=1, le=365),
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Daily cost_saved for the last N days."""
    data = await get_savings_timeline(db, org_id, days)
    return [SavingsTimelinePoint(**d) for d in data]


@router.get("/top-agents", response_model=list[TopAgentEntry])
async def top_agents(
    limit: int = Query(10, ge=1, le=50),
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Top N costliest agents."""
    data = await get_top_agents(db, org_id, limit)
    return [TopAgentEntry(**d) for d in data]


@router.get("/incident-distribution", response_model=list[IncidentDistribution])
async def incident_distribution(
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Incident count by type with percentages."""
    data = await get_incident_distribution(db, org_id)
    return [IncidentDistribution(**d) for d in data]


@router.get("/carbon-report", response_model=CarbonReport)
async def carbon_report(
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """Carbon impact report: total kWh, CO2, equivalences, monthly trend."""
    data = await get_carbon_report(db, org_id)
    return CarbonReport(
        total_kwh_saved=data["total_kwh_saved"],
        total_co2_saved_kg=data["total_co2_saved_kg"],
        equivalences=CarbonImpact(**data["equivalences"]),
        monthly_trend=data["monthly_trend"],
    )


@router.get("/heatmap", response_model=HeatmapResponse)
async def heatmap(
    org_id: UUID = Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    """7x24 activity matrix (day of week x hour of day)."""
    data = await get_heatmap(db, org_id)
    return HeatmapResponse(**data)
