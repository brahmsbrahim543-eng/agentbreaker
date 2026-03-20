from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AgentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_id: str
    name: str
    status: str
    current_risk_score: float
    total_cost: float
    total_tokens: int
    total_steps: int
    total_co2_grams: float
    total_kwh: float
    last_seen_at: datetime | None


class AgentDetail(AgentResponse):
    recent_steps: list = []
    risk_breakdown: dict | None = None


class AgentListResponse(BaseModel):
    items: list[AgentResponse]
    total: int
    page: int
    per_page: int
