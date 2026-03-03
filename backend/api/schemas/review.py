"""Review schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class IssueSchema(BaseModel):
    """Issue item from agent output."""

    category: str
    severity: str
    title: str
    description: str
    file_path: str | None = None
    line: int | None = None


class SuggestionSchema(BaseModel):
    """Code suggestion item."""

    title: str
    rationale: str
    suggested_patch: str | None = None


class ReviewCreate(BaseModel):
    """Manual review creation schema."""

    pull_request_id: UUID
    model_used: str | None = "gpt-4o"


class ReviewSummary(BaseModel):
    """Compact review details."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    overall_score: float
    security_score: float
    standards_score: float
    quality_score: float
    created_at: datetime


class ReviewResponse(BaseModel):
    """Detailed review response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pull_request_id: UUID
    status: str
    overall_score: float
    security_score: float
    standards_score: float
    quality_score: float
    summary: str | None
    issues: list[IssueSchema] = Field(default_factory=list)
    suggestions: list[SuggestionSchema] = Field(default_factory=list)
    model_used: str | None
    tokens_used: int
    processing_time_ms: int
    created_at: datetime
    completed_at: datetime | None


class ReviewListResponse(BaseModel):
    """Paginated review response."""

    items: list[ReviewSummary]
    total: int
    page: int
    page_size: int
