"""Pull request model."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


class PullRequestState(str, enum.Enum):
    """Pull request state enum."""

    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class PullRequest(Base):
    """Pull request tracked by CodeSentinel."""

    __tablename__ = "pull_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    github_pr_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    head_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[PullRequestState] = mapped_column(Enum(PullRequestState), default=PullRequestState.OPEN, nullable=False)
    additions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    repository_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True)

    repository = relationship("Repository", back_populates="pull_requests")
    review = relationship("Review", back_populates="pull_request", uselist=False, cascade="all, delete-orphan")
