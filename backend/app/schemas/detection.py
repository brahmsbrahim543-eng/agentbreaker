from pydantic import BaseModel


class RiskScoreBreakdown(BaseModel):
    similarity: float
    diminishing_returns: float
    context_inflation: float
    error_cascade: float
    cost_velocity: float
    composite: float


class DetectionResult(BaseModel):
    score: float
    flag: str | None = None
    detail: str


class AnalysisResponse(BaseModel):
    step_number: int
    risk_score: float
    risk_breakdown: RiskScoreBreakdown
    action: str
    warnings: list[str]
    carbon_impact: dict | None = None
