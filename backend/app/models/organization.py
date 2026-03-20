import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(
        String(20), nullable=False, default="free"
    )  # free | pro | enterprise
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    users: Mapped[list["User"]] = relationship(  # noqa: F821
        "User", back_populates="organization", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        "Project", back_populates="organization", cascade="all, delete-orphan"
    )
    subscription: Mapped["Subscription | None"] = relationship(  # noqa: F821
        "Subscription", back_populates="organization", uselist=False, cascade="all, delete-orphan"
    )
