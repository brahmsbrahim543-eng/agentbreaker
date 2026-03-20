from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_id: UUID
    agent_name: str
    incident_type: str
    risk_score_at_kill: float
    cost_avoided: float
    co2_avoided_grams: float
    steps_at_kill: int
    created_at: datetime


class IncidentDetail(IncidentResponse):
    snapshot: dict
    kill_reason_detail: str


class IncidentListResponse(BaseModel):
    items: list[IncidentResponse]
    total: int
    page: int
    per_page: int


class IncidentStats(BaseModel):
    total_count: int
    by_type: dict[str, int]
    total_cost_avoided: float
    total_co2_avoided_grams: float
