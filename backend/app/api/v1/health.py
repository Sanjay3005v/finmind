"""Liveness/readiness endpoints. No auth, no rate limiting."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.rate_limit import check_redis_connection
from app.db.session import check_db_connection

router = APIRouter(tags=["health"])

# Indirected through module-level callables so tests can monkeypatch
# `app.api.v1.health.db_check` / `redis_check` without touching real infra.
db_check: Callable = check_db_connection
redis_check: Callable = check_redis_connection


@router.get("/health")
async def health() -> dict:
    """Liveness only — always 200 if the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready() -> JSONResponse:
    """Readiness — checks DB and Redis connectivity."""
    db_ok = await db_check()
    redis_ok = await redis_check()
    checks = {
        "database": "ok" if db_ok else "failed",
        "redis": "ok" if redis_ok else "failed",
    }
    overall_ok = db_ok and redis_ok
    return JSONResponse(
        status_code=status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "ready" if overall_ok else "not_ready", "checks": checks},
    )
