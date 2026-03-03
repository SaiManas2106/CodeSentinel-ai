"""Review routes."""

from __future__ import annotations

import uuid
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.models.pull_request import PullRequest
from backend.api.models.repository import Repository
from backend.api.models.review import Review, ReviewStatus
from backend.api.routes.auth import get_current_user
from backend.api.schemas.review import ReviewListResponse, ReviewResponse, ReviewSummary
from backend.api.models.user import User
from backend.core.database import get_db

router = APIRouter(tags=["reviews"])


@router.get("/reviews", response_model=ReviewListResponse)
async def list_reviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: ReviewStatus | None = None,
    min_score: float | None = Query(None, ge=0, le=100),
    max_score: float | None = Query(None, ge=0, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReviewListResponse:
    filters = [Repository.user_id == current_user.id]
    if status:
        filters.append(Review.status == status)
    if min_score is not None:
        filters.append(Review.overall_score >= min_score)
    if max_score is not None:
        filters.append(Review.overall_score <= max_score)

    query = (
        select(Review)
        .join(PullRequest, Review.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(and_(*filters))
        .order_by(Review.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    count_query = (
        select(func.count(Review.id))
        .join(PullRequest, Review.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(and_(*filters))
    )

    reviews = (await db.execute(query)).scalars().all()
    total = int((await db.execute(count_query)).scalar_one())
    return ReviewListResponse(items=[ReviewSummary.model_validate(r) for r in reviews], total=total, page=page, page_size=page_size)


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReviewResponse:
    review = await db.scalar(
        select(Review)
        .join(PullRequest, Review.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(Review.id == review_id, Repository.user_id == current_user.id)
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return ReviewResponse.model_validate(review)


@router.get("/repositories/{repo_id}/reviews", response_model=ReviewListResponse)
async def repo_reviews(repo_id: uuid.UUID, page: int = 1, page_size: int = 20, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReviewListResponse:
    query = (
        select(Review)
        .join(PullRequest, PullRequest.id == Review.pull_request_id)
        .join(Repository, Repository.id == PullRequest.repository_id)
        .where(Repository.id == repo_id, Repository.user_id == current_user.id)
        .order_by(Review.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    reviews = (await db.execute(query)).scalars().all()
    total = int(
        (
            await db.execute(
                select(func.count(Review.id))
                .join(PullRequest, PullRequest.id == Review.pull_request_id)
                .join(Repository, Repository.id == PullRequest.repository_id)
                .where(Repository.id == repo_id, Repository.user_id == current_user.id)
            )
        ).scalar_one()
    )
    return ReviewListResponse(items=[ReviewSummary.model_validate(r) for r in reviews], total=total, page=page, page_size=page_size)


@router.post("/reviews/{review_id}/retry")
async def retry_review(review_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, str]:
    review = await db.scalar(
        select(Review)
        .join(PullRequest, Review.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(Review.id == review_id, Repository.user_id == current_user.id)
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.status = ReviewStatus.PENDING
    await db.commit()
    return {"status": "queued"}


@router.get("/reviews/stats/summary")
async def review_stats(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, float | int]:
    base = (
        select(Review)
        .join(PullRequest, Review.pull_request_id == PullRequest.id)
        .join(Repository, PullRequest.repository_id == Repository.id)
        .where(Repository.user_id == current_user.id)
        .subquery()
    )
    metrics = await db.execute(
        select(
            func.count(base.c.id),
            func.avg(base.c.overall_score),
            func.avg(base.c.security_score),
            func.avg(base.c.standards_score),
            func.avg(base.c.quality_score),
        )
    )
    count, overall, security, standards, quality = metrics.one()
    return {
        "total_reviews": int(count or 0),
        "avg_overall_score": float(overall or 0),
        "avg_security_score": float(security or 0),
        "avg_standards_score": float(standards or 0),
        "avg_quality_score": float(quality or 0),
    }
