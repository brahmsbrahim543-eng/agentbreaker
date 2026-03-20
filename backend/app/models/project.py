import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID, JSONType


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    budget_limit: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_cost_per_agent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_steps_per_agent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detection_thresholds: Mapped[Optional[dict]] = mapped_column(JSONType, nullable=True)
    carbon_region: Mapped[str] = mapped_column(
        String(50), nullable=False, default="us-east"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(  # noqa: F821
        "Organization", back_populates="projects"
    )
    agents: Mapped[list["Agent"]] = relationship(  # noqa: F821
        "Agent", back_populates="project", cascade="all, delete-orphan"
    )
    incidents: Mapped[list["Incident"]] = relationship(  # noqa: F821
        "Incident", back_populates="project", cascade="all, delete-orphan"
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(  # noqa: F821
        "ApiKey", back_populates="project", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["Metric"]] = relationship(  # noqa: F821
        "Metric", back_populates="project", cascade="all, delete-orphan"
    )
