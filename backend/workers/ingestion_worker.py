"""Repository ingestion worker."""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import httpx
from celery import shared_task
from redis.asyncio import Redis
from sqlalchemy import select

from backend.api.models.repository import Repository
from backend.core.config import get_settings
from backend.core.database import AsyncSessionLocal
from backend.core.logging import get_logger
from backend.rag.pipeline import RAGPipeline

settings = get_settings()
logger = get_logger(__name__)


async def _clone_or_pull(repo_url: str, target_path: Path, github_token: str) -> Path:
    if target_path.exists() and (target_path / ".git").exists():
        return target_path
    authenticated_url = repo_url.replace("https://", f"https://x-access-token:{github_token}@")
    proc = await asyncio.create_subprocess_exec("git", "clone", authenticated_url, str(target_path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to clone repository: {stderr.decode('utf-8', errors='ignore')}")
    return target_path


@shared_task(name="backend.workers.ingestion_worker.ingest_repository_task")
def ingest_repository_task(repo_id: str, repo_path: str = "") -> dict[str, str | int | float]:
    """Ingest repository into Qdrant for retrieval context."""
    return asyncio.run(_ingest_repository_task(repo_id=repo_id, repo_path=repo_path))


async def _ingest_repository_task(repo_id: str, repo_path: str = "") -> dict[str, str | int | float]:
    redis_client = Redis.from_url(settings.redis.url, decode_responses=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="codesentinel-ingest-"))

    try:
        async with AsyncSessionLocal() as db:
            repo = await db.scalar(select(Repository).where(Repository.id == repo_id))
            if not repo:
                raise ValueError("Repository not found")

            await redis_client.hset(f"ingestion:{repo_id}", mapping={"status": "cloning", "progress": "10"})
            if repo_path:
                local_path = Path(repo_path)
            else:
                github_url = f"https://github.com/{repo.full_name}.git"
                local_path = await _clone_or_pull(github_url, tmp_dir / repo.full_name.replace("/", "_"), repo.user.github_access_token if repo.user else "")

            await redis_client.hset(f"ingestion:{repo_id}", mapping={"status": "embedding", "progress": "50"})
            from qdrant_client import AsyncQdrantClient

            qdrant = AsyncQdrantClient(host=settings.qdrant.host, port=settings.qdrant.port, api_key=settings.qdrant.api_key or None)
            pipeline = RAGPipeline(redis_client=Redis.from_url(settings.redis.url), qdrant_client=qdrant)
            metrics = await pipeline.ingest_repository(str(local_path), str(repo.id))

            repo.last_synced_at = datetime.now(UTC)
            await db.commit()

            await redis_client.hset(f"ingestion:{repo_id}", mapping={"status": "completed", "progress": "100"})
            return {"status": "completed", **metrics}
    except Exception as exc:
        logger.exception("ingestion.failed", repo_id=repo_id, error=str(exc))
        await redis_client.hset(f"ingestion:{repo_id}", mapping={"status": "failed", "error": str(exc)})
        raise
    finally:
        await redis_client.close()
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir, ignore_errors=True)


@shared_task(name="backend.workers.ingestion_worker.cleanup_progress")
def cleanup_progress() -> None:
    """Cleanup old ingestion progress keys."""
    asyncio.run(_cleanup_progress())


async def _cleanup_progress() -> None:
    redis_client = Redis.from_url(settings.redis.url, decode_responses=True)
    keys = [key async for key in redis_client.scan_iter(match="ingestion:*")]
    for key in keys:
        await redis_client.expire(key, 3600)
    await redis_client.close()
