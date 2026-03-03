"""Repository routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.models.pull_request import PullRequest
from backend.api.models.repository import Repository
from backend.api.models.review import Review
from backend.api.models.user import User
from backend.api.routes.auth import get_current_user
from backend.core.database import get_db

router = APIRouter(prefix="/repositories", tags=["repositories"])


@router.get("")
async def list_repositories(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[dict[str, str | bool | None]]:
    repos = (await db.execute(select(Repository).where(Repository.user_id == current_user.id))).scalars().all()
    return [
        {
            "id": str(repo.id),
            "full_name": repo.full_name,
            "language": repo.language,
            "is_active": repo.is_active,
            "last_synced_at": repo.last_synced_at.isoformat() if repo.last_synced_at else None,
        }
        for repo in repos
    ]


@router.post("")
async def connect_repository(payload: dict[str, str | int], db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, str]:
    required = {"github_repo_id", "full_name", "owner"}
    if not required.issubset(payload.keys()):
        raise HTTPException(status_code=400, detail="Missing repository fields")

    existing = await db.scalar(select(Repository).where(Repository.github_repo_id == int(payload["github_repo_id"])))
    if existing:
        raise HTTPException(status_code=409, detail="Repository already connected")

    repo = Repository(
        github_repo_id=int(payload["github_repo_id"]),
        full_name=str(payload["full_name"]),
        owner=str(payload["owner"]),
        description=str(payload.get("description", "")) or None,
        language=str(payload.get("language", "")) or None,
        default_branch=str(payload.get("default_branch", "main")),
        is_private=bool(payload.get("is_private", True)),
        is_active=True,
        webhook_id=str(payload.get("webhook_id", "")) or None,
        installation_id=str(payload.get("installation_id", "")) or None,
        user_id=current_user.id,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return {"id": str(repo.id), "status": "connected"}


@router.delete("/{repo_id}")
async def disconnect_repository(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, str]:
    repo = await db.scalar(select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id))
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    await db.delete(repo)
    await db.commit()
    return {"status": "disconnected"}


@router.post("/{repo_id}/sync")
async def sync_repository(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, str]:
    repo = await db.scalar(select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id))
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    repo.last_synced_at = datetime.now(UTC)
    await db.commit()
    return {"status": "sync_triggered"}


@router.get("/{repo_id}/stats")
async def repository_stats(repo_id: uuid.UUID, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, float | int]:
    repo = await db.scalar(select(Repository).where(Repository.id == repo_id, Repository.user_id == current_user.id))
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    pr_count = int((await db.execute(select(func.count(PullRequest.id)).where(PullRequest.repository_id == repo_id))).scalar_one())
    avg_score = float(
        (
            await db.execute(
                select(func.avg(Review.overall_score))
                .join(PullRequest, PullRequest.id == Review.pull_request_id)
                .where(PullRequest.repository_id == repo_id)
            )
        ).scalar()
        or 0
    )
    review_count = int(
        (
            await db.execute(
                select(func.count(Review.id))
                .join(PullRequest, PullRequest.id == Review.pull_request_id)
                .where(PullRequest.repository_id == repo_id)
            )
        ).scalar_one()
    )

    return {"pull_requests": pr_count, "reviews": review_count, "avg_score": avg_score}
