"""Broker connection orchestration: create/list/sync/disconnect.

Ownership is checked here too (not just in the router's dependency) per the
"defense in depth" rule in `docs/ARCHITECTURE.md` section 4 — a caller that
somehow reaches these functions without going through the FastAPI
dependency chain still cannot touch another user's connection.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.brokers.registry import get_adapter
from app.core.crypto import decrypt_credentials, encrypt_credentials
from app.core.errors import AppError
from app.models.broker_connection import BrokerConnection
from app.models.holding import Holding
from app.models.portfolio import Portfolio

DEFAULT_PORTFOLIO_NAME = "Default Portfolio"


async def _get_owned_connection(db: AsyncSession, connection_id: UUID, user_id: UUID) -> BrokerConnection:
    result = await db.execute(
        select(BrokerConnection).where(BrokerConnection.id == connection_id, BrokerConnection.user_id == user_id)
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise AppError(code="BROKER_CONNECTION_NOT_FOUND", message="Broker connection not found.", status_code=404)
    return connection


async def _get_or_create_default_portfolio(db: AsyncSession, user_id: UUID) -> Portfolio:
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == user_id, Portfolio.is_default.is_(True))
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is not None:
        return portfolio

    result = await db.execute(select(Portfolio).where(Portfolio.user_id == user_id).order_by(Portfolio.created_at))
    portfolio = result.scalars().first()
    if portfolio is not None:
        return portfolio

    portfolio = Portfolio(user_id=user_id, name=DEFAULT_PORTFOLIO_NAME, is_default=True)
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


async def create_connection(
    db: AsyncSession,
    user_id: UUID,
    broker: str,
    mode: Optional[str] = None,
    credentials: Optional[dict] = None,
    label: Optional[str] = None,
) -> BrokerConnection:
    """Every new row defaults to `mode='paper'` unless the caller explicitly
    passes `mode='live'` — paper is structurally the default, never
    auto-promoted."""
    resolved_mode = mode or "paper"
    encrypted = encrypt_credentials(credentials) if credentials else None
    # Paper connections don't need a real broker session to be usable
    # immediately; live connections stay 'disconnected' until a later,
    # separate authenticate/callback flow (out of scope for this phase).
    status = "connected" if resolved_mode == "paper" else "disconnected"

    connection = BrokerConnection(
        user_id=user_id,
        broker=broker,
        mode=resolved_mode,
        status=status,
        encrypted_credentials=encrypted,
        label=label,
    )
    db.add(connection)
    await db.flush()
    await db.refresh(connection)
    return connection


async def list_connections(db: AsyncSession, user_id: UUID) -> list[BrokerConnection]:
    """Callers must serialize results through `BrokerConnectionResponse`
    (which has no `encrypted_credentials` field) — never return the ORM
    object's raw bytea column to a client."""
    result = await db.execute(
        select(BrokerConnection).where(BrokerConnection.user_id == user_id).order_by(BrokerConnection.created_at)
    )
    return list(result.scalars().all())


async def sync_holdings(db: AsyncSession, connection_id: UUID, user_id: UUID) -> tuple[BrokerConnection, int]:
    """Calls the adapter for this connection and upserts the returned
    holdings into the user's default (or first) portfolio.

    # NOTE: this runs synchronously inline with the request for now. A later
    # phase should move this behind a Celery task (see
    # docs/ARCHITECTURE.md's `workers/` module) so a slow/rate-limited
    # broker call doesn't block the HTTP request.
    """
    connection = await _get_owned_connection(db, connection_id, user_id)

    credentials: Optional[dict] = None
    if connection.mode == "live" and connection.encrypted_credentials:
        # Decrypted only in-memory, right before the adapter needs it. Never
        # logged, never persisted back out.
        credentials = decrypt_credentials(connection.encrypted_credentials)

    adapter = get_adapter(connection.broker, connection.mode, credentials)
    holdings = await adapter.get_holdings()

    portfolio = await _get_or_create_default_portfolio(db, user_id)

    synced = 0
    for dto in holdings:
        result = await db.execute(
            select(Holding).where(
                Holding.portfolio_id == portfolio.id,
                Holding.symbol == dto.symbol,
                Holding.exchange == dto.exchange,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.quantity = dto.quantity
            existing.avg_price = dto.avg_price
            existing.current_price = dto.current_price
            existing.asset_class = dto.asset_class
            existing.sector = dto.sector
            existing.currency = dto.currency
            existing.broker_connection_id = connection.id
        else:
            db.add(
                Holding(
                    portfolio_id=portfolio.id,
                    broker_connection_id=connection.id,
                    symbol=dto.symbol,
                    exchange=dto.exchange,
                    quantity=dto.quantity,
                    avg_price=dto.avg_price,
                    current_price=dto.current_price,
                    asset_class=dto.asset_class,
                    sector=dto.sector,
                    currency=dto.currency,
                )
            )
        synced += 1

    connection.last_synced_at = datetime.now(timezone.utc)
    connection.status = "connected"
    await db.flush()
    await db.refresh(connection)
    return connection, synced


async def disconnect(db: AsyncSession, connection_id: UUID, user_id: UUID) -> None:
    connection = await _get_owned_connection(db, connection_id, user_id)
    await db.delete(connection)
    await db.flush()
