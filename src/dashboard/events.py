"""Live progress over Redis pub/sub.

The worker publishes per-day events on ``sim:{job_id}`` (synchronously, from the
simulation thread); the FastAPI SSE endpoint subscribes and forwards them to the
browser. Terminal events (``done``/``failed``/``interrupted``) close the stream.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

import redis
import redis.asyncio as aioredis

TERMINAL = {"done", "failed", "interrupted"}


def redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379")


def channel(job_id: str) -> str:
    return f"sim:{job_id}"


_sync: redis.Redis | None = None


def publish(job_id: str, event: dict) -> None:
    """Synchronous publish — safe to call from the simulation worker thread."""
    global _sync
    if _sync is None:
        _sync = redis.from_url(redis_url())
    _sync.publish(channel(job_id), json.dumps(event))


async def subscribe(client: aioredis.Redis, job_id: str) -> AsyncIterator[dict]:
    """Yield events for a job until a terminal one arrives, then stop."""
    pubsub = client.pubsub()
    await pubsub.subscribe(channel(job_id))
    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            event = json.loads(message["data"])
            yield event
            if event.get("type") in TERMINAL:
                return
    finally:
        await pubsub.unsubscribe(channel(job_id))
        await pubsub.aclose()


def sse(event: dict) -> str:
    """Format one event as a Server-Sent Event frame."""
    return f"data: {json.dumps(event)}\n\n"
