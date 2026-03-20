"""Ingest route -- the critical step ingestion endpoint authenticated by API key."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis_pool
from app.api.v1.deps import verify_api_key_dep
from app.schemas.step import StepCreate
from app.schemas.detection import AnalysisResponse, RiskScoreBreakdown
from app.services.ingest import process_step

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/step", response_model=AnalysisResponse)
async def ingest_step(
    body: StepCreate,
    project_id: UUID = Depends(verify_api_key_dep),
    db: AsyncSession = Depends(get_db),
):
    """Ingest a single agent step and run it through the detection pipeline.

    Authenticated via X-API-Key header. Returns real-time risk analysis.
    """
    # Get Redis for event publishing (graceful fallback if unavailable)
    redis = None
    try:
        redis = get_redis_pool()
    except RuntimeError:
        pass

    result = await process_step(
        db=db,
        project_id=project_id,
        step_data=body,
        redis=redis,
    )

    return AnalysisResponse(
        step_number=result["step_number"],
        risk_score=result["risk_score"],
        risk_breakdown=RiskScoreBreakdown(**result["risk_breakdown"]),
        action=result["action"],
        warnings=result["warnings"],
        carbon_impact=result.get("carbon_impact"),
    )
