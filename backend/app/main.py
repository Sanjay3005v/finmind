"""FastAPI app factory for FINMIND's backend."""
from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if sys.platform == "win32":
    # Defensive fallback for entrypoints other than uvicorn (e.g. a bare
    # `python -c` import, a future worker script) that create their loop via
    # the ambient policy. uvicorn itself does NOT respect this policy — its
    # "asyncio" loop setup hardcodes `asyncio.ProactorEventLoop` on win32
    # regardless — so running the server actually requires the explicit
    # `--loop app.core.loop:selector_event_loop_factory` flag (see
    # app/core/loop.py) since psycopg's async mode cannot run on
    # ProactorEventLoop at all.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.agents.checkpoint import CheckpointerProvider
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestContextMiddleware, configure_logging

logger = structlog.get_logger(__name__)

# One process-wide provider, owning the Postgres connection pool that backs
# the LangGraph checkpointer (app/agents/checkpoint.py). Started/stopped by
# the lifespan below; requests reach it via the `get_checkpointer` FastAPI
# dependency, which tests override with a `MemorySaver` instead.
checkpointer_provider = CheckpointerProvider()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    # Never open a real Postgres connection from the automated test suite —
    # pytest sets PYTEST_CURRENT_TEST for the duration of every test
    # (including fixture setup), so this reliably detects "running under
    # pytest" without any extra test-only configuration.
    if "PYTEST_CURRENT_TEST" not in os.environ and settings.DATABASE_URL:
        try:
            await checkpointer_provider.startup()
        except Exception as exc:  # noqa: BLE001 — never block app startup on this
            logger.warning("agent_checkpointer_startup_failed", error=str(exc))

    app.state.checkpointer_provider = checkpointer_provider
    yield
    await checkpointer_provider.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="FINMIND API",
        version="0.1.0",
        description="AI investment research & portfolio analyst — backend, including the LangGraph agent layer (Phase 6).",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
