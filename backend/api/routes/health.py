"""Health routes."""

from __future__ import annotations

import time

from aiokafka import AIOKafkaProducer
from fastapi import APIRouter, Request
from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from backend.core.database import check_database_health

router = APIRouter(tags=["health"])


async def _timed_check(name: str, check_fn) -> dict[str, str | float]:
    start = time.perf_counter()
    ok = await check_fn()
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    return {"service": name, "status": "healthy" if ok else "unhealthy", "response_time_ms": duration_ms}


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    redis_client: Redis = request.app.state.redis
    qdrant_client: AsyncQdrantClient = request.app.state.qdrant
    kafka_producer: AIOKafkaProducer = request.app.state.kafka_producer
    mongo_client: AsyncIOMotorClient = request.app.state.mongo

    async def db_check() -> bool:
        return await check_database_health()

    async def redis_check() -> bool:
        pong = await redis_client.ping()
        return bool(pong)

    async def qdrant_check() -> bool:
        await qdrant_client.get_collections()
        return True

    async def kafka_check() -> bool:
        return bool(kafka_producer.bootstrap_connected())

    async def mongo_check() -> bool:
        result = await mongo_client.admin.command("ping")
        return result.get("ok", 0) == 1

    checks = [
        await _timed_check("postgresql", db_check),
        await _timed_check("redis", redis_check),
        await _timed_check("qdrant", qdrant_check),
        await _timed_check("kafka", kafka_check),
        await _timed_check("mongodb", mongo_check),
    ]

    overall = "healthy" if all(c["status"] == "healthy" for c in checks) else "degraded"
    return {"status": overall, "services": checks}
