"""Trade approvals — the human-in-the-loop gate before any order is placed
(docs/API_CONTRACTS.md "Trade approvals" section; docs/ARCHITECTURE.md
section 4). Only the owning user may decide on their own trade approval.

Hard rule (Phase 6 spec rule #2): this is the ONLY code path that ever calls
a broker adapter's `place_order` for an agent-proposed trade, and it only
ever does so in `mode="paper"` — live trading isn't wired up yet (Phase 4
scope). The LangGraph agent (`app/agents/graph.py`) never calls a broker
itself; it only creates the `pending` row and `interrupt()`s.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.checkpoint import get_checkpointer
from app.api.v1.deps import get_owned_trade_approval, parse_user_uuid
from app.brokers.registry import get_adapter
from app.brokers.schemas import OrderRequest
from app.core.errors import AppError
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.agent_session import AgentSession
from app.models.broker_connection import BrokerConnection
from app.models.trade_approval import TradeApproval
from app.models.transaction import Transaction
from app.schemas.trade_approval import TradeApprovalResponse, TradeDecisionRequest
from app.services import agent_service

router = APIRouter(prefix="/trade-approvals", tags=["trade-approvals"], dependencies=[Depends(rate_limit_dependency)])


@router.get("", response_model=list[TradeApprovalResponse])
async def list_trade_approvals(
    status: Optional[str] = Query(default=None),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[TradeApproval]:
    owner_uuid = parse_user_uuid(user_id)
    query = select(TradeApproval).where(TradeApproval.user_id == owner_uuid)
    if status:
        query = query.where(TradeApproval.status == status)
    result = await db.execute(query.order_by(TradeApproval.created_at.desc()))
    return list(result.scalars().all())


@router.get("/{id}", response_model=TradeApprovalResponse)
async def get_trade_approval(approval: TradeApproval = Depends(get_owned_trade_approval)) -> TradeApproval:
    return approval


@router.post("/{id}/decision", response_model=TradeApprovalResponse)
async def decide_trade_approval(
    payload: TradeDecisionRequest,
    approval: TradeApproval = Depends(get_owned_trade_approval),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
) -> TradeApproval:
    if approval.status != "pending":
        raise AppError(
            code="TRADE_APPROVAL_ALREADY_DECIDED",
            message=f"This trade approval is already '{approval.status}' and cannot be decided again.",
            status_code=400,
        )

    approval.decided_at = datetime.now(timezone.utc)

    if payload.decision == "approve":
        broker_label = "paper"
        if approval.broker_connection_id is not None:
            connection = await db.get(BrokerConnection, approval.broker_connection_id)
            if connection is not None:
                broker_label = connection.broker

        # ALWAYS paper mode here — see module docstring (rule #2).
        adapter = get_adapter(broker_label, mode="paper")
        order = await adapter.place_order(
            OrderRequest(
                symbol=approval.symbol,
                exchange=approval.exchange,
                side=approval.side,
                quantity=float(approval.quantity),
                order_type=approval.order_type,
                limit_price=float(approval.limit_price) if approval.limit_price is not None else None,
            )
        )
        approval.status = "executed"
        approval.broker_order_id = order.broker_order_id
        approval.executed_at = datetime.now(timezone.utc)

        # Record the (paper) fill in the portfolio ledger too, same as a
        # manual/broker-synced transaction, but tagged `source='agent_trade'`.
        if approval.session_id is not None:
            session_row = await db.get(AgentSession, approval.session_id)
            if session_row is not None and session_row.portfolio_id is not None:
                db.add(
                    Transaction(
                        portfolio_id=session_row.portfolio_id,
                        symbol=order.symbol,
                        exchange=order.exchange,
                        side=order.side,
                        quantity=order.quantity,
                        price=order.price or 0,
                        fees=0,
                        executed_at=order.timestamp or approval.executed_at,
                        source="agent_trade",
                        broker_order_id=order.broker_order_id,
                    )
                )
    else:
        approval.status = "rejected"
        if payload.note:
            approval.risk_checks = {**(approval.risk_checks or {}), "decision_note": payload.note}

    await db.flush()
    await db.refresh(approval)

    if approval.session_id is not None:
        # Triggers the graph resume right now so the agent's acknowledgment
        # is persisted immediately — this endpoint's own response stays a
        # plain TradeApprovalResponse (not SSE), per API_CONTRACTS.md. A
        # later call to `POST /agents/sessions/{id}/resume` is a safe no-op
        # if this already resumed it (see agent_service.resume_session).
        async for _event in agent_service.resume_session(db, str(approval.session_id), user_id, checkpointer):
            pass

    return approval
