"""Shared pytest fixtures for DB-backed API tests.

We never hit the real (Supabase) `DATABASE_URL` from automated tests. Instead
we spin up an in-memory SQLite database per test, scoped to just the tables
the broker-connections feature touches (`auth.users` stub, `portfolios`,
`broker_connections`, `holdings`) — the full `Base.metadata` also contains
Postgres-only column types (pgvector, JSONB) that SQLite can't render, and
we don't need those tables for this feature's tests.

`auth.users` is modeled with `schema="auth"` (see
`app/models/_supabase_auth_stub.py`) purely for FK resolution against the
real Postgres schema; SQLite has no notion of schemas, so we `ATTACH
DATABASE ':memory:' AS auth` on every new connection and keep all
connections pinned to the same in-memory database via `StaticPool`.
"""
from __future__ import annotations

import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.agents.checkpoint import get_checkpointer
from app.db.session import Base, get_db
from app.main import app
from app.core.security import get_current_user_id
from app.models._supabase_auth_stub import auth_users
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.broker_connection import BrokerConnection
from app.models.document import Document
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.trade_approval import TradeApproval
from app.models.transaction import Transaction

TEST_TABLES = [
    auth_users,
    Portfolio.__table__,
    BrokerConnection.__table__,
    Holding.__table__,
    Transaction.__table__,
    Document.__table__,
    AgentSession.__table__,
]

# `document_chunks` (docs/DATABASE_SCHEMA.sql) uses two Postgres-only column
# features SQLite's type compiler can't render at all: a pgvector `vector`
# column and a `tsvector` GENERATED ALWAYS AS column computed via
# `to_tsvector()`. We create a SQLite-compatible physical table by hand
# (TEXT columns standing in for `vector`/`tsvector`) instead of going
# through `Base.metadata.create_all` for this one table. The ORM model
# (`app.models.document_chunk.DocumentChunk`) is unchanged — SQLAlchemy
# compiles INSERT/SELECT against its real column list (computed columns
# like `tsv` are automatically excluded from INSERT), so ordinary ORM usage
# in ingestion tests works unmodified. Hybrid retrieval's raw pgvector/tsv
# SQL (`app/rag/retrieval.py`) is Postgres-only and is not exercised against
# this SQLite table — see `tests/test_retrieval.py`, which only tests the
# pure `reciprocal_rank_fusion` function.
_DOCUMENT_CHUNKS_DDL = """
    CREATE TABLE document_chunks (
        id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        document_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        embedding TEXT,
        tsv TEXT,
        metadata TEXT NOT NULL DEFAULT ('{}'),
        created_at TEXT DEFAULT (CURRENT_TIMESTAMP)
    )
"""

# `agent_messages.tool_calls`/`citations` and `trade_approvals.risk_checks`
# are Postgres `JSONB` — same problem as `document_chunks.metadata` above,
# same fix: a hand-written SQLite-compatible physical table (TEXT standing
# in for JSONB), ORM model unchanged. SQLAlchemy's JSONB type still
# serializes/deserializes Python dict/list values through this TEXT column
# on SQLite (verified directly), so ordinary ORM usage in the agent tests
# works unmodified.
_AGENT_MESSAGES_DDL = """
    CREATE TABLE agent_messages (
        id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        tool_calls TEXT,
        citations TEXT,
        created_at TEXT DEFAULT (CURRENT_TIMESTAMP)
    )
"""

_TRADE_APPROVALS_DDL = """
    CREATE TABLE trade_approvals (
        id TEXT PRIMARY KEY DEFAULT (gen_random_uuid()),
        session_id TEXT,
        user_id TEXT NOT NULL,
        broker_connection_id TEXT,
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL DEFAULT ('NSE'),
        side TEXT NOT NULL,
        quantity NUMERIC NOT NULL,
        order_type TEXT NOT NULL DEFAULT ('market'),
        limit_price NUMERIC,
        status TEXT NOT NULL DEFAULT ('pending'),
        requested_by TEXT NOT NULL DEFAULT ('agent'),
        reasoning TEXT,
        risk_checks TEXT NOT NULL DEFAULT ('{}'),
        broker_order_id TEXT,
        created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
        decided_at TEXT,
        executed_at TEXT
    )
"""

TEST_USER_ID = uuid.uuid4()


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _setup_sqlite_connection(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("ATTACH DATABASE ':memory:' AS auth")
        cursor.close()
        # Postgres' pgcrypto `gen_random_uuid()` (used as every table's
        # `id` server_default) has no SQLite equivalent — register it as a
        # SQL function so ORM inserts that rely on the server default still
        # get a real UUID instead of erroring. Must return the *hex, no
        # dashes* form: `postgresql.UUID(as_uuid=True)`'s bind/result
        # processors store/compare values in that form on non-Postgres
        # dialects, so a dash-formatted default would insert fine but then
        # fail every subsequent lookup-by-primary-key (refresh/get/etc.)
        # with a silent id mismatch.
        dbapi_connection.create_function("gen_random_uuid", 0, lambda: uuid.uuid4().hex)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=TEST_TABLES)
        await conn.exec_driver_sql(_DOCUMENT_CHUNKS_DDL)
        await conn.exec_driver_sql(_AGENT_MESSAGES_DDL)
        await conn.exec_driver_sql(_TRADE_APPROVALS_DDL)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session


@pytest.fixture
def client(db_engine) -> TestClient:
    """A TestClient with `get_db`, `get_current_user_id`, and
    `get_checkpointer` overridden so no real Supabase Postgres connection,
    JWT verification, or LangGraph Postgres checkpointer is ever needed.

    `get_checkpointer` is overridden with a single `MemorySaver` instance
    shared across every request this TestClient makes in one test — that
    instance identity matters: LangGraph looks up a thread's saved state by
    object identity/storage inside the saver, so a send-message call and a
    later resume call within the same test must see the SAME MemorySaver,
    not a fresh one per request (mirrors how `db_engine` is one shared
    in-memory SQLite database for the whole test, not one per request)."""
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False, class_=AsyncSession)
    memory_checkpointer = MemorySaver()

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def _override_get_current_user_id() -> str:
        return str(TEST_USER_ID)

    async def _override_get_checkpointer():
        return memory_checkpointer

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user_id] = _override_get_current_user_id
    app.dependency_overrides[get_checkpointer] = _override_get_checkpointer

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
