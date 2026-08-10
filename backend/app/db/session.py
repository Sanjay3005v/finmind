"""Async SQLAlchemy engine/session plumbing.

Engine + session-factory creation is lazy: constructing `create_async_engine`
does not open a network connection, so importing this module (or the whole
app) never fails even if `DATABASE_URL` is an unreachable placeholder.
Connection failures surface per-request, inside `get_db` / `check_db_connection`.
"""
from __future__ import annotations

from typing import AsyncGenerator, Optional

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    pass


_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        # Supabase's Session pooler caps a project at 15 concurrent
        # connections total, shared across every client (this app, any
        # migration/admin script, etc). SQLAlchemy's un-capped default
        # (pool_size=5 + max_overflow=10 = 15) can exhaust that budget by
        # itself under bursty traffic, locking out anything else — including
        # `alembic` — until connections are recycled. Stay well under it.
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=3,
            max_overflow=2,
            pool_recycle=300,
            future=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, class_=AsyncSession
        )
    return _session_factory


def override_engine(engine: AsyncEngine) -> None:
    """Test helper: swap in a different engine (e.g. sqlite+aiosqlite) and
    rebuild the session factory to match."""
    global _engine, _session_factory
    _engine = engine
    _session_factory = async_sessionmaker(bind=_engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_db_connection() -> bool:
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("db_health_check_failed", error=str(exc))
        return False
