import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_project_id_external_id", "project_id", "external_id", unique=True),
        Index("ix_agents_project_id_status", "project_id", "status"),
        Index("ix_agents_project_id_current_risk_score", "project_id", "current_risk_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id"), nullable=False
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="idle"
    )  # running | warning | killed | idle | completed
    current_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_co2_grams: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    project: Mapped["Project"] = relationship(  # noqa: F821
        "Project", back_populates="agents"
    )
    steps: Mapped[list["Step"]] = relationship(  # noqa: F821
        "Step", back_populates="agent", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["Incident"]] = relationship(  # noqa: F821
        "Incident", back_populates="agent", cascade="all, delete-orphan"
    )
