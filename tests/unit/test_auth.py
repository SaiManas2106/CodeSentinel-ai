"""Security and auth tests."""

from __future__ import annotations

import pytest
from redis.asyncio import Redis

from backend.core.security import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_github_webhook_signature,
    verify_password,
)


def test_jwt_create_verify() -> None:
    token = create_access_token("user-1")
    payload = decode_token(token)
    assert payload["sub"] == "user-1"
    assert payload["type"] == "access"


def test_password_hashing() -> None:
    raw = "StrongPassword123!"
    hashed = hash_password(raw)
    assert verify_password(raw, hashed)


def test_webhook_signature_verification() -> None:
    payload = b'{"ping":true}'
    secret = "abc123"
    import hmac, hashlib

    signature = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_github_webhook_signature(payload, signature, secret=secret)


@pytest.mark.asyncio
async def test_refresh_blacklist_flow() -> None:
    redis_client = Redis.from_url("redis://localhost:6379/0")
    token = create_refresh_token("user-2")
    await blacklist_token(redis_client, token)
    assert await redis_client.get(f"blacklist:{token}") is not None
    await redis_client.delete(f"blacklist:{token}")
    await redis_client.close()
