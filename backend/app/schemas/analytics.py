from pydantic import BaseModel


class OverviewResponse(BaseModel):
    total_savings: float
    active_agents: int
    incidents_today: int
    avg_risk_score: float


class SavingsTimelinePoint(BaseModel):
    date: str
    cost_saved: float


class TopAgentEntry(BaseModel):
    agent_name: str
    total_cost: float


class IncidentDistribution(BaseModel):
    type: str
    count: int
    percentage: float


class HeatmapResponse(BaseModel):
    data: list[list[int]]
    labels_x: list[str]
    labels_y: list[str]
