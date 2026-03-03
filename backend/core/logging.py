"""Structured logging configuration for CodeSentinel."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Callable

import structlog
from fastapi import Request, Response

from backend.core.config import Settings

request_id_context: ContextVar[str] = ContextVar("request_id", default="")
correlation_id_context: ContextVar[str] = ContextVar("correlation_id", default="")


class RequestContextMiddleware:
    """Inject request and correlation IDs into request context."""

    def __init__(self, app: Callable):
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        headers = {k.decode("utf-8"): v.decode("utf-8") for k, v in scope.get("headers", [])}
        correlation_id = headers.get("x-correlation-id", request_id)

        request_id_context.set(request_id)
        correlation_id_context.set(correlation_id)

        async def send_wrapper(message: dict) -> None:
            if message.get("type") == "http.response.start":
                headers_list = message.setdefault("headers", [])
                headers_list.append((b"x-request-id", request_id.encode("utf-8")))
                headers_list.append((b"x-correlation-id", correlation_id.encode("utf-8")))
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _add_context(_: object, __: str, event_dict: dict) -> dict:
    event_dict["request_id"] = request_id_context.get("")
    event_dict["correlation_id"] = correlation_id_context.get("")
    return event_dict


def configure_logging(settings: Settings) -> None:
    """Configure stdlib and structlog."""
    logging.basicConfig(stream=sys.stdout, level=getattr(logging, settings.log_level, logging.INFO), format="%(message)s")

    processors: list[Callable] = [
        structlog.contextvars.merge_contextvars,
        _add_context,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.app_env == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return structlog logger instance."""
    return structlog.get_logger(name)
