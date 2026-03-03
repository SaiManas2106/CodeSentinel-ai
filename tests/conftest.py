"""Shared test fixtures."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from testcontainers.postgres import PostgresContainer

from backend.main import app


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    container = PostgresContainer("pgvector/pgvector:pg16")
    container.start()
    try:
        yield container
    finally:
        container.stop()


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    client = Redis.from_url("redis://localhost:6379/0")
    yield client
    await client.close()


@pytest.fixture
def mock_github_api(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    data = {
        "token": "gho_test",
        "user": {"id": 123, "login": "tester", "email": "tester@example.com", "avatar_url": "https://example.com/avatar.png"},
    }
    return data


@pytest.fixture
def test_user() -> dict[str, str]:
    return {"id": "00000000-0000-0000-0000-000000000001", "username": "tester"}


@pytest.fixture
def test_repo() -> dict[str, str]:
    return {"id": "00000000-0000-0000-0000-000000000002", "full_name": "org/repo"}
