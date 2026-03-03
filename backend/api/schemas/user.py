"""User and auth schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    """User registration schema."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """User update schema."""

    username: str | None = Field(default=None, min_length=3, max_length=100)
    avatar_url: str | None = None


class UserResponse(BaseModel):
    """Public user schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    username: str
    github_username: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class GitHubOAuthCallback(BaseModel):
    """GitHub OAuth callback schema."""

    code: str
    state: str | None = None


class TokenPair(BaseModel):
    """Access/refresh token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Refresh token request."""

    refresh_token: str


class TokenPayload(BaseModel):
    """Token payload schema."""

    sub: str
    type: str
    exp: int
    iat: int
