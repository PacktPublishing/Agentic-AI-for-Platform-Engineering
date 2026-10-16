"""Configure the pinned Langfuse v2 client.

The runtime creates a request trace; PolicyValidationHook adds authorization
metadata without recording bearer tokens or complete tool arguments.
"""

from __future__ import annotations

import logging

from .settings import settings

logger = logging.getLogger("agent.telemetry")

_client = None


def configure() -> None:
    global _client
    if not settings.langfuse_enabled:
        logger.info("telemetry: langfuse disabled (env vars not set)")
        return

    from langfuse import Langfuse

    _client = Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
    logger.info(
        "telemetry: langfuse client active",
        extra={"host": settings.langfuse_host, "agent_id": settings.agent_id},
    )


def client():
    return _client


def flush() -> None:
    if _client is not None:
        _client.flush()
