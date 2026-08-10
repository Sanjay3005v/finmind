"""Shared route dependencies for the v1 API."""
from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.agent_session import AgentSession
from app.models.broker_connection import BrokerConnection
from app.models.document import Document
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.trade_approval import TradeApproval


def parse_user_uuid(user_id: str) -> UUID:
    try:
        return UUID(user_id)
    except (ValueError, AttributeError, TypeError) as exc:
        raise AppError(code="INVALID_TOKEN", message="Token subject is not a valid UUID.", status_code=401) from exc


async def get_owned_portfolio(
    id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Portfolio:
    """Loads the `Portfolio` identified by the `{id}` path param, scoped to
    the authenticated user. Returns 404 (never 403) if the portfolio belongs
    to someone else, so we never leak whether the id exists at all."""
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(
        select(Portfolio).where(Portfolio.id == id, Portfolio.user_id == owner_uuid)
    )
    portfolio = result.scalar_one_or_none()
    if portfolio is None:
        raise AppError(code="PORTFOLIO_NOT_FOUND", message="Portfolio not found.", status_code=404)
    return portfolio


async def get_owned_broker_connection(
    id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> BrokerConnection:
    """Loads the `BrokerConnection` identified by the `{id}` path param,
    scoped to the authenticated user. Returns 404 (never 403) if the
    connection belongs to someone else, so we never leak whether the id
    exists at all — same pattern as `get_owned_portfolio`."""
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(
        select(BrokerConnection).where(BrokerConnection.id == id, BrokerConnection.user_id == owner_uuid)
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise AppError(
            code="BROKER_CONNECTION_NOT_FOUND", message="Broker connection not found.", status_code=404
        )
    return connection


async def get_visible_document(
    id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Loads the `Document` identified by the `{id}` path param if it is
    visible to the caller — owned by them, or shared/global (`user_id IS
    NULL`) — matching the RLS policy semantics in docs/DATABASE_SCHEMA.sql.
    Returns 404 (never 403) otherwise, same not-found-not-leaked pattern as
    `get_owned_portfolio`."""
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(
        select(Document).where(
            Document.id == id, or_(Document.user_id == owner_uuid, Document.user_id.is_(None))
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise AppError(code="DOCUMENT_NOT_FOUND", message="Document not found.", status_code=404)
    return document


async def get_owned_document(
    id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Document:
    """Loads the `Document` identified by the `{id}` path param, scoped to
    documents actually owned by the caller (excludes shared/global
    documents, which nobody may delete). Returns 404 (never 403) if the
    document belongs to someone else or is shared, so we never leak
    existence — same pattern as `get_owned_portfolio`."""
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(select(Document).where(Document.id == id, Document.user_id == owner_uuid))
    document = result.scalar_one_or_none()
    if document is None:
        raise AppError(code="DOCUMENT_NOT_FOUND", message="Document not found.", status_code=404)
    return document


async def get_owned_holding(
    id: UUID,
    holding_id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Holding:
    """Loads the `Holding` identified by `{holding_id}` within the portfolio
    identified by `{id}`, scoped to the authenticated user via a join on
    `portfolios.user_id`. Returns 404 (never 403) if the holding doesn't
    exist, belongs to a different portfolio, or that portfolio belongs to
    someone else — same not-found-not-leaked pattern as `get_owned_portfolio`."""
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(
        select(Holding)
        .join(Portfolio, Holding.portfolio_id == Portfolio.id)
        .where(Holding.id == holding_id, Holding.portfolio_id == id, Portfolio.user_id == owner_uuid)
    )
    holding = result.scalar_one_or_none()
    if holding is None:
        raise AppError(code="HOLDING_NOT_FOUND", message="Holding not found.", status_code=404)
    return holding


async def get_owned_agent_session(
    id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AgentSession:
    """Loads the `AgentSession` identified by the `{id}` path param, scoped
    to the authenticated user. Returns 404 (never 403) if the session
    belongs to someone else — same not-found-not-leaked pattern as
    `get_owned_portfolio`."""
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(select(AgentSession).where(AgentSession.id == id, AgentSession.user_id == owner_uuid))
    session = result.scalar_one_or_none()
    if session is None:
        raise AppError(code="AGENT_SESSION_NOT_FOUND", message="Agent session not found.", status_code=404)
    return session


async def get_owned_trade_approval(
    id: UUID,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> TradeApproval:
    """Loads the `TradeApproval` identified by the `{id}` path param, scoped
    to the authenticated user — only the owning user may view or decide on
    it (docs/ARCHITECTURE.md section 4). Returns 404 (never 403) if it
    belongs to someone else."""
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(select(TradeApproval).where(TradeApproval.id == id, TradeApproval.user_id == owner_uuid))
    approval = result.scalar_one_or_none()
    if approval is None:
        raise AppError(code="TRADE_APPROVAL_NOT_FOUND", message="Trade approval not found.", status_code=404)
    return approval
