"""Security helpers for authentication and webhook validation."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from redis.asyncio import Redis

from backend.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
settings = get_settings()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hash."""
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt.secret_key, algorithm=settings.jwt.algorithm)


def create_access_token(subject: str) -> str:
    """Create signed access token."""
    return _create_token(subject, "access", timedelta(minutes=settings.jwt.access_token_expire_minutes))


def create_refresh_token(subject: str) -> str:
    """Create signed refresh token."""
    return _create_token(subject, "refresh", timedelta(days=settings.jwt.refresh_token_expire_days))


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify JWT token."""
    try:
        return jwt.decode(token, settings.jwt.secret_key, algorithms=[settings.jwt.algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc


async def blacklist_token(redis_client: Redis, token: str) -> None:
    """Blacklist refresh token in Redis until its expiry."""
    payload = decode_token(token)
    exp = int(payload["exp"])
    ttl = max(1, exp - int(datetime.now(UTC).timestamp()))
    await redis_client.setex(f"blacklist:{token}", ttl, "1")


async def is_token_blacklisted(redis_client: Redis, token: str) -> bool:
    """Check if token is blacklisted."""
    value = await redis_client.get(f"blacklist:{token}")
    return value is not None


def generate_github_app_jwt() -> str:
    """Generate GitHub App JWT signed with private key."""
    now = datetime.now(UTC)
    payload = {
        "iat": int((now - timedelta(seconds=60)).timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "iss": settings.github.app_id,
    }
    return jwt.encode(payload, settings.github.app_private_key, algorithm="RS256")


def verify_github_webhook_signature(payload: bytes, signature_header: str, secret: str | None = None) -> bool:
    """Verify GitHub webhook HMAC SHA-256 signature."""
    webhook_secret = (secret or settings.github.webhook_secret).encode("utf-8")
    expected = "sha256=" + hmac.new(webhook_secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
