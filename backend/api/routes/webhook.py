"""GitHub webhook routes."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from aiokafka import AIOKafkaProducer
from fastapi import APIRouter, HTTPException, Request, status

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.core.security import verify_github_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
settings = get_settings()
logger = get_logger(__name__)


@router.post("/github")
async def github_webhook(request: Request) -> dict[str, str]:
    payload_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    event = request.headers.get("X-GitHub-Event", "unknown")

    if not verify_github_webhook_signature(payload_bytes, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    body: dict[str, Any] = json.loads(payload_bytes.decode("utf-8"))
    action = body.get("action", "")

    logger.info("webhook.received", event=event, action=action)

    if event == "ping":
        return {"status": "ok", "message": "pong"}

    if event == "installation" and action in {"created", "deleted"}:
        logger.info("webhook.installation", action=action, installation=body.get("installation", {}).get("id"))

    if event == "pull_request" and action in {"opened", "synchronize", "reopened"}:
        producer: AIOKafkaProducer = request.app.state.kafka_producer
        message = {
            "event": event,
            "action": action,
            "repository": body.get("repository", {}),
            "pull_request": body.get("pull_request", {}),
            "installation": body.get("installation", {}),
            "received_at": datetime.now(UTC).isoformat(),
        }
        await producer.send_and_wait(settings.kafka.pr_review_topic, json.dumps(message).encode("utf-8"))

    return {"status": "accepted"}
