import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID, JSONType


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        Index("ix_incidents_project_id_created_at", "project_id", "created_at"),
        Index("ix_incidents_project_id_incident_type", "project_id", "incident_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agents.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id"), nullable=False
    )
    incident_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # semantic_loop | diminishing_returns | context_bloat | error_cascade | cost_spike | composite
    risk_score_at_kill: Mapped[float] = mapped_column(Float, nullable=False)
    cost_at_kill: Mapped[float] = mapped_column(Float, nullable=False)
    cost_avoided: Mapped[float] = mapped_column(Float, nullable=False)
    co2_avoided_grams: Mapped[float] = mapped_column(Float, nullable=False)
    kwh_avoided: Mapped[float] = mapped_column(Float, nullable=False)
    steps_at_kill: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    kill_reason_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(  # noqa: F821
        "Agent", back_populates="incidents"
    )
    project: Mapped["Project"] = relationship(  # noqa: F821
        "Project", back_populates="incidents"
    )
