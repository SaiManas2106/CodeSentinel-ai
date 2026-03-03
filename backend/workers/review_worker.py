"""Review worker consuming Kafka review requests."""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from aiokafka import AIOKafkaConsumer
from celery import shared_task
from redis.asyncio import Redis
from sqlalchemy import select

from backend.agents.orchestrator import ReviewOrchestrator
from backend.api.models.pull_request import PullRequest
from backend.api.models.review import Review, ReviewStatus
from backend.core.config import get_settings
from backend.core.database import AsyncSessionLocal
from backend.core.logging import get_logger
from backend.rag.pipeline import RAGPipeline

settings = get_settings()
logger = get_logger(__name__)


async def _post_github_review_comment(repo_full_name: str, pr_number: int, github_token: str, review_text: str) -> None:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(
            f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments",
            headers={"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github+json"},
            json={"body": review_text},
        )
        response.raise_for_status()


async def process_pr_review(event: dict[str, Any]) -> None:
    """End-to-end PR review processing task."""
    start = time.perf_counter()
    redis_client = Redis.from_url(settings.redis.url, decode_responses=False)

    async with AsyncSessionLocal() as db:
        review_id = event.get("review_id")
        review = await db.scalar(select(Review).where(Review.id == review_id)) if review_id else None
        if review:
            review.status = ReviewStatus.PROCESSING
            await db.commit()

        try:
            repo = event["repository"]
            pr = event["pull_request"]
            diff_url = pr["diff_url"]
            token = event.get("github_access_token", "")

            async with httpx.AsyncClient(timeout=30.0) as client:
                diff_resp = await client.get(diff_url, headers={"Authorization": f"Bearer {token}"})
                diff_resp.raise_for_status()
                diff_text = diff_resp.text

            from qdrant_client import AsyncQdrantClient

            qdrant = AsyncQdrantClient(host=settings.qdrant.host, port=settings.qdrant.port, api_key=settings.qdrant.api_key or None)
            rag = RAGPipeline(redis_client=redis_client, qdrant_client=qdrant)
            orchestrator = ReviewOrchestrator(rag)

            state = await orchestrator.run(
                {
                    "pr_diff": diff_text,
                    "pr_metadata": {
                        "title": pr.get("title", ""),
                        "repository_id": str(repo.get("id", "")),
                        "repository": repo.get("full_name", ""),
                    },
                    "metadata": {},
                }
            )

            final = state.get("final_review", {})
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            if review:
                review.status = ReviewStatus.COMPLETED
                review.summary = final.get("summary", "Review completed")
                review.overall_score = float(final.get("overall_score", 0))
                review.security_score = float(final.get("security_score", 0))
                review.standards_score = float(final.get("standards_score", 0))
                review.quality_score = float(final.get("quality_score", 0))
                review.issues = final.get("issues", [])
                review.suggestions = final.get("suggestions", [])
                review.model_used = final.get("model_used", settings.openai.openai_model)
                review.tokens_used = int(final.get("tokens_used", 0))
                review.processing_time_ms = elapsed_ms
                review.completed_at = datetime.now(UTC)
                await db.commit()

            comment = f"## CodeSentinel AI Review\n\nScore: {final.get('overall_score', 0)}\n\n{final.get('summary', 'No summary')}"
            await _post_github_review_comment(repo["full_name"], int(pr["number"]), token, comment)
            await redis_client.publish("notifications", json.dumps({"type": "review_completed", "pr": pr.get("number")}))

            logger.info("review.processed", pr=pr.get("number"), elapsed_ms=elapsed_ms)
        except Exception as exc:
            logger.exception("review.failed", error=str(exc))
            if review:
                review.status = ReviewStatus.FAILED
                review.summary = f"Review failed: {exc}"
                review.completed_at = datetime.now(UTC)
                await db.commit()
        finally:
            await redis_client.close()


@shared_task(name="backend.workers.review_worker.process_review_event")
def process_review_event(event: dict[str, Any]) -> None:
    """Celery entrypoint for async review processing."""
    asyncio.run(process_pr_review(event))


async def consume_review_requests() -> None:
    """Kafka consumer loop for review requests."""
    consumer = AIOKafkaConsumer(
        settings.kafka.pr_review_topic,
        bootstrap_servers=settings.kafka.bootstrap_servers,
        group_id=settings.kafka.consumer_group,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        enable_auto_commit=True,
    )
    await consumer.start()
    try:
        async for message in consumer:
            process_review_event.delay(message.value)
    finally:
        await consumer.stop()
