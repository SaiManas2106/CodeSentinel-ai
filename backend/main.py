"""FastAPI entrypoint for CodeSentinel AI backend."""

from __future__ import annotations

from contextlib import asynccontextmanager

import sentry_sdk
from aiokafka import AIOKafkaProducer
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from prometheus_fastapi_instrumentator import Instrumentator
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis

from backend.api.routes import auth, health, repositories, reviews, webhook
from backend.core.config import get_settings
from backend.core.database import register_pgvector_extension
from backend.core.logging import RequestContextMiddleware, configure_logging, get_logger

settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)

if settings.sentry.dsn:
    sentry_sdk.init(dsn=settings.sentry.dsn, traces_sample_rate=settings.sentry.traces_sample_rate, environment=settings.app_env)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown shared resources."""
    logger.info("app.startup")
    await register_pgvector_extension()

    app.state.redis = Redis.from_url(settings.redis.url, decode_responses=False)
    app.state.qdrant = AsyncQdrantClient(host=settings.qdrant.host, port=settings.qdrant.port, api_key=settings.qdrant.api_key or None)
    app.state.mongo = AsyncIOMotorClient(settings.mongo.uri)

    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka.bootstrap_servers)
    await producer.start()
    app.state.kafka_producer = producer

    yield

    logger.info("app.shutdown")
    await app.state.kafka_producer.stop()
    await app.state.redis.close()
    app.state.mongo.close()


app = FastAPI(title=settings.app_name, docs_url="/docs", openapi_url="/openapi.json", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(health.router)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(webhook.router, prefix=settings.api_v1_prefix)
app.include_router(reviews.router, prefix=settings.api_v1_prefix)
app.include_router(repositories.router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    """Root health endpoint."""
    return {"status": "ok", "service": settings.app_name}
