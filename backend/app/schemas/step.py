from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StepCreate(BaseModel):
    agent_id: str
    input: str
    output: str
    tokens: int = Field(..., ge=0)
    cost: float = Field(..., ge=0)
    tool: str | None = None
    duration_ms: int | None = None
    context_size: int | None = None
    error_message: str | None = None


class StepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_number: int
    input_preview: str
    output_preview: str
    tokens_used: int
    cost: float
    tool_name: str | None
    error_message: str | None
    created_at: datetime
