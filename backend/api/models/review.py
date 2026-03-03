"""Review model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class ReviewStatus(str, enum.Enum):
    """Review status enum."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Review(Base):
    """AI review result for a pull request."""

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pull_request_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), default=ReviewStatus.PENDING, nullable=False, index=True)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    security_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    standards_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    suggestions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(255))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processing_time_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pull_request = relationship("PullRequest", back_populates="review")
