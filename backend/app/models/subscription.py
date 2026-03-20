import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    stripe_customer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free"
    )  # free | starter | growth | enterprise
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | past_due | canceled | trialing
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_projects: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_agents: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    monthly_price_eur: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    organization: Mapped["Organization"] = relationship(  # noqa: F821
        "Organization", back_populates="subscription"
    )
