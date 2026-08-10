"""LangGraph checkpointer lifecycle.

Production runs the Postgres-backed checkpointer (`AsyncPostgresSaver`) so a
trade proposal's `interrupt()` can sit paused for hours/days awaiting human
approval and resume exactly where it left off (docs/ARCHITECTURE.md section
5). Tests use `MemorySaver` instead — the FastAPI dependency
`get_checkpointer` (see `app/api/v1/agents.py`) is overridden in
`tests/conftest.py` exactly the way `get_db`/`get_current_user_id` already
are, so the automated suite never opens a real Postgres connection.
"""
from __future__ import annotations

from typing import Optional

import structlog
from fastapi import Request
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


def to_psycopg_dsn(database_url: str) -> str:
    """Converts SQLAlchemy's `postgresql+asyncpg://...` URL into the plain
    `postgresql://...` DSN psycopg expects. `psycopg` is a separate driver
    from the `asyncpg` one SQLAlchemy uses elsewhere in the app — the two
    coexist fine since they only ever touch the same Postgres instance
    through independent connections."""
    if database_url.startswith("postgresql+asyncpg://"):
        return "postgresql://" + database_url[len("postgresql+asyncpg://") :]
    if database_url.startswith("postgres+asyncpg://"):
        return "postgresql://" + database_url[len("postgres+asyncpg://") :]
    return database_url


class CheckpointerProvider:
    """Owns the lifecycle of the Postgres connection pool backing
    `AsyncPostgresSaver`. `startup()` opens the pool and runs `.setup()`
    once (creating LangGraph's own `langgraph_*` tables); `shutdown()`
    closes it. `get()` returns a fresh lightweight `AsyncPostgresSaver`
    wrapper around the shared pool for each call (cheap — the pool itself,
    not the wrapper, holds the real connections), or falls back to a
    process-wide `MemorySaver` if Postgres was never configured."""

    def __init__(self) -> None:
        self._pool: Optional[AsyncConnectionPool] = None
        self._memory = MemorySaver()

    async def startup(self) -> None:
        settings = get_settings()
        dsn = to_psycopg_dsn(settings.DATABASE_URL)
        pool = AsyncConnectionPool(dsn, open=False, kwargs={"autocommit": True})
        await pool.open()
        saver = AsyncPostgresSaver(pool)
        await saver.setup()
        self._pool = pool
        logger.info("agent_checkpointer_setup_complete")

    async def shutdown(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def get(self) -> BaseCheckpointSaver:
        if self._pool is not None:
            return AsyncPostgresSaver(self._pool)
        return self._memory


async def get_checkpointer(request: Request) -> BaseCheckpointSaver:
    """FastAPI dependency used by `app/api/v1/agents.py` and
    `app/api/v1/trade_approvals.py`. In production this returns a
    Postgres-backed saver (via the `CheckpointerProvider` set up in
    `app/main.py`'s lifespan); `tests/conftest.py` overrides this exact
    dependency with a per-test `MemorySaver` singleton — the same override
    mechanism already used for `get_db`/`get_current_user_id` — so the
    automated suite never opens a real Postgres connection for LangGraph
    checkpointing."""
    provider: Optional[CheckpointerProvider] = getattr(request.app.state, "checkpointer_provider", None)
    if provider is None:
        return MemorySaver()
    return provider.get()
