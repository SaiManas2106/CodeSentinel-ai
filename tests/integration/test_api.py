"""Integration API tests."""

from __future__ import annotations

import json

import pytest


@pytest.mark.asyncio
async def test_health_endpoint(async_client) -> None:
    response = await async_client.get("/health")
    assert response.status_code in (200, 503)


@pytest.mark.asyncio
async def test_webhook_endpoint(async_client, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.api.routes import webhook

    monkeypatch.setattr(webhook, "verify_github_webhook_signature", lambda *_args, **_kwargs: True)

    payload = {
        "action": "opened",
        "repository": {"id": 1, "full_name": "org/repo"},
        "pull_request": {"number": 1},
        "installation": {"id": 99}
    }
    response = await async_client.post(
        "/api/v1/webhooks/github",
        headers={"X-Hub-Signature-256": "sha256=test", "X-GitHub-Event": "pull_request"},
        content=json.dumps(payload),
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_reviews_list_unauthorized(async_client) -> None:
    response = await async_client.get("/api/v1/reviews")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_auth_refresh_validation(async_client) -> None:
    response = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": "bad.token"})
    assert response.status_code in (401, 422)
