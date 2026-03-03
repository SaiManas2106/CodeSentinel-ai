"""Authentication routes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.models.audit_log import AuditLog
from backend.api.models.user import User
from backend.api.schemas.user import TokenPair, TokenRefresh, UserResponse
from backend.core.config import get_settings
from backend.core.database import get_db
from backend.core.security import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_token_blacklisted,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


async def _rate_limit(redis_client: Redis, key: str, limit: int = 10, window_seconds: int = 900) -> None:
    now = int(datetime.now(UTC).timestamp())
    window_start = now - window_seconds
    pipe = redis_client.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zadd(key, {str(now): now})
    pipe.expire(key, window_seconds)
    pipe.zcard(key)
    _, _, _, count = await pipe.execute()
    if int(count) > limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")


async def _audit(
    db: AsyncSession,
    action: str,
    request: Request,
    user_id: uuid.UUID | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type="auth",
        resource_id=str(user_id) if user_id else "anonymous",
        metadata=metadata or {},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.add(entry)
    await db.commit()


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> User:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = auth_header.split(" ", maxsplit=1)[1]
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user = await db.scalar(select(User).where(User.id == uuid.UUID(payload["sub"])))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.get("/github")
async def github_login() -> RedirectResponse:
    params = {
        "client_id": settings.github.client_id,
        "redirect_uri": str(settings.github.redirect_uri),
        "scope": "repo read:user user:email",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"https://github.com/login/oauth/authorize?{query}")


@router.get("/github/callback", response_model=TokenPair)
async def github_callback(code: str, request: Request, db: AsyncSession = Depends(get_db)) -> TokenPair:
    redis_client: Redis = request.app.state.redis
    await _rate_limit(redis_client, f"auth:github:{request.client.host if request.client else 'unknown'}")

    async with httpx.AsyncClient(timeout=15.0) as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github.client_id,
                "client_secret": settings.github.client_secret,
                "code": code,
                "redirect_uri": str(settings.github.redirect_uri),
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub token exchange failed")

        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/vnd.github+json"},
        )
        user_resp.raise_for_status()
        gh_user = user_resp.json()

    existing = await db.scalar(select(User).where(User.github_id == str(gh_user["id"])))
    if existing:
        existing.github_access_token = access_token
        existing.github_username = gh_user.get("login")
        existing.avatar_url = gh_user.get("avatar_url")
        user = existing
    else:
        random_password = hash_password(uuid.uuid4().hex + uuid.uuid4().hex)
        user = User(
            email=gh_user.get("email") or f"{gh_user['login']}@users.noreply.github.com",
            username=gh_user["login"],
            hashed_password=random_password,
            github_id=str(gh_user["id"]),
            github_username=gh_user.get("login"),
            github_access_token=access_token,
            avatar_url=gh_user.get("avatar_url"),
            is_active=True,
            is_verified=True,
        )
        db.add(user)

    await db.commit()
    await db.refresh(user)
    await _audit(db, "github_oauth_callback", request, user_id=user.id)

    return TokenPair(access_token=create_access_token(str(user.id)), refresh_token=create_refresh_token(str(user.id)))


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(payload: TokenRefresh, request: Request, db: AsyncSession = Depends(get_db)) -> TokenPair:
    redis_client: Redis = request.app.state.redis
    await _rate_limit(redis_client, f"auth:refresh:{request.client.host if request.client else 'unknown'}")
    if await is_token_blacklisted(redis_client, payload.refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token blacklisted")

    decoded = decode_token(payload.refresh_token)
    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = decoded["sub"]
    user = await db.scalar(select(User).where(User.id == uuid.UUID(user_id)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    await _audit(db, "token_refresh", request, user_id=user.id)
    return TokenPair(access_token=create_access_token(user_id), refresh_token=create_refresh_token(user_id))


@router.post("/logout")
async def logout(payload: TokenRefresh, request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    redis_client: Redis = request.app.state.redis
    await blacklist_token(redis_client, payload.refresh_token)
    decoded = decode_token(payload.refresh_token)
    user_id = uuid.UUID(decoded["sub"]) if decoded.get("sub") else None
    await _audit(db, "logout", request, user_id=user_id)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user), request: Request = None, db: AsyncSession = Depends(get_db)) -> UserResponse:
    if request is not None:
        await _audit(db, "me", request, user_id=current_user.id)
    return UserResponse.model_validate(current_user)
