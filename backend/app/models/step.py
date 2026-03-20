import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Float, Integer, DateTime, Text, ForeignKey, Index, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class Step(Base):
    __tablename__ = "steps"
    __table_args__ = (
        Index("ix_steps_agent_id_step_number", "agent_id", "step_number", unique=True),
        Index("ix_steps_agent_id_created_at", "agent_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("agents.id"), nullable=False
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_embedding: Mapped[Optional[bytes]] = mapped_column(LargeBinary, nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    context_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    unique_token_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    agent: Mapped["Agent"] = relationship(  # noqa: F821
        "Agent", back_populates="steps"
    )
