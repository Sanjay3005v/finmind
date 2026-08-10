"""Redis-backed sliding-window rate limiting.

Keyed by authenticated user id when available (set on `request.state.user_id`
by `app.core.security`), otherwise by client IP. Configurable via
`RATE_LIMIT_PER_MINUTE`. If Redis is unreachable we fail OPEN (log a warning,
let the request through) rather than 500ing every request.
"""
from __future__ import annotations

import time
from typing import Optional

import structlog
from fastapi import Request
from redis import asyncio as aioredis

from app.core.config import get_settings
from app.core.errors import AppError

logger = structlog.get_logger(__name__)

_redis_client: Optional[aioredis.Redis] = None


def get_redis_client() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True, socket_connect_timeout=0.5, socket_timeout=0.5
        )
    return _redis_client


async def check_redis_connection() -> bool:
    try:
        client = get_redis_client()
        await client.ping()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("redis_ping_failed", error=str(exc))
        return False


async def _sliding_window_count(client: aioredis.Redis, key: str, window_seconds: int) -> int:
    now = time.time()
    window_start = now - window_seconds
    async with client.pipeline(transaction=True) as pipe:
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {f"{now}:{id(now)}": now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        _, _, count, _ = await pipe.execute()
    return int(count)


async def enforce_rate_limit(identity: str, limit: int, window_seconds: int = 60) -> None:
    """Raises AppError(429) if `identity` has exceeded `limit` requests within
    `window_seconds`. Fails open (returns silently) on any Redis error."""
    redis_key = f"ratelimit:{identity}"
    try:
        client = get_redis_client()
        count = await _sliding_window_count(client, redis_key, window_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("rate_limit_check_failed_open", identity=identity, error=str(exc))
        return

    if count > limit:
        raise AppError(
            code="RATE_LIMIT_EXCEEDED",
            message="Too many requests. Please slow down and try again shortly.",
            status_code=429,
        )


async def rate_limit_dependency(request: Request) -> None:
    settings = get_settings()
    identity = getattr(request.state, "user_id", None)
    if not identity:
        identity = request.client.host if request.client else "unknown"
    await enforce_rate_limit(identity, settings.RATE_LIMIT_PER_MINUTE, window_seconds=60)
