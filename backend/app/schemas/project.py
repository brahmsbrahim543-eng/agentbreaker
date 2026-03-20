from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    budget_limit: float | None = None
    max_cost_per_agent: float | None = None
    max_steps_per_agent: int | None = None
    detection_thresholds: dict | None = None
    carbon_region: str = "us-east"


class ProjectUpdate(BaseModel):
    name: str | None = None
    budget_limit: float | None = None
    max_cost_per_agent: float | None = None
    max_steps_per_agent: int | None = None
    detection_thresholds: dict | None = None
    carbon_region: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    org_id: UUID
    name: str
    slug: str
    budget_limit: float | None
    max_cost_per_agent: float | None
    max_steps_per_agent: int | None
    detection_thresholds: dict | None
    carbon_region: str
    created_at: datetime
    updated_at: datetime
