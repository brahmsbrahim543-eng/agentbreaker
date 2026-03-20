import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, Integer, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class Metric(Base):
    __tablename__ = "metrics"
    __table_args__ = (
        Index("ix_metrics_project_id_timestamp", "project_id", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    active_agents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False)
    total_savings: Mapped[float] = mapped_column(Float, nullable=False)
    total_incidents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_co2_saved_grams: Mapped[float] = mapped_column(Float, nullable=False)
    total_kwh_saved: Mapped[float] = mapped_column(Float, nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship(  # noqa: F821
        "Project", back_populates="metrics"
    )
