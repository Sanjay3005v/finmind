"""Agent session orchestration: create/list sessions, message history, and
running/resuming the LangGraph agent (`app/agents/graph.py`).

Streaming design: `send_message`/`resume_session` drive the compiled graph
with `stream_mode="updates"` and translate its output into the SSE event
shapes from docs/API_CONTRACTS.md (`token`/`tool_call`/`citation`/
`interrupt`/`done`). Only the FINAL accepted tool_results/citations/
draft_answer (i.e. after self-reflection has either passed or given up) are
surfaced to the client — intermediate drafts that self-reflection rejected
are never shown, only used internally to produce the next attempt. "token"
events are the final answer chunked into small word-groups; this is not
literal per-token streaming from the underlying LLM API (the narration call
is a single `ainvoke`, not `.stream()`), but it satisfies the same SSE
contract shape the frontend renders against.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Optional
from uuid import UUID

import structlog
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_graph
from app.agents.tools import build_tools
from app.core.errors import AppError
from app.models.agent_message import AgentMessage
from app.models.agent_session import AgentSession
from app.models.trade_approval import TradeApproval

logger = structlog.get_logger(__name__)

_TOKEN_CHUNK_WORDS = 6


@dataclass
class StreamEvent:
    event: str
    data: dict


async def _get_owned_session(db: AsyncSession, session_id: str, user_id: str) -> AgentSession:
    result = await db.execute(
        select(AgentSession).where(AgentSession.id == UUID(session_id), AgentSession.user_id == UUID(user_id))
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise AppError(code="AGENT_SESSION_NOT_FOUND", message="Agent session not found.", status_code=404)
    return session


async def create_session(
    db: AsyncSession, user_id: str, portfolio_id: Optional[str] = None, title: Optional[str] = None
) -> AgentSession:
    session = AgentSession(
        user_id=UUID(user_id),
        portfolio_id=UUID(portfolio_id) if portfolio_id else None,
        title=title or "New research session",
    )
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession, user_id: str) -> list[AgentSession]:
    result = await db.execute(
        select(AgentSession).where(AgentSession.user_id == UUID(user_id)).order_by(AgentSession.created_at.desc())
    )
    return list(result.scalars().all())


async def get_messages(db: AsyncSession, session_id: str, user_id: str) -> list[AgentMessage]:
    await _get_owned_session(db, session_id, user_id)  # ownership check, 404 if not owned
    result = await db.execute(
        select(AgentMessage).where(AgentMessage.session_id == UUID(session_id)).order_by(AgentMessage.created_at)
    )
    return list(result.scalars().all())


def _thread_config(session_id: str, tools: dict, db: AsyncSession) -> dict:
    return {"configurable": {"thread_id": str(session_id), "tools": tools, "db": db}}


async def _persist_and_stream(
    db: AsyncSession, session: AgentSession, graph, config: dict, stream_input: Any
) -> AsyncIterator[StreamEvent]:
    latest_tool_results: list[dict] = []
    latest_citations: list[dict] = []
    latest_draft = ""
    interrupted_payload: Optional[dict] = None

    async for chunk in graph.astream(stream_input, config, stream_mode="updates"):
        if "__interrupt__" in chunk:
            interrupts = chunk["__interrupt__"]
            interrupted_payload = interrupts[0].value if interrupts else {}
            break
        for _node_name, update in chunk.items():
            if not isinstance(update, dict):
                continue
            if update.get("tool_results") is not None:
                latest_tool_results = update["tool_results"]
            if update.get("citations") is not None:
                latest_citations = update["citations"]
            if update.get("draft_answer") is not None:
                latest_draft = update["draft_answer"]

    if interrupted_payload is not None:
        side = interrupted_payload.get("side", "")
        quantity = interrupted_payload.get("quantity", "")
        symbol = interrupted_payload.get("symbol", "")
        content = f"I'd like to {side} {quantity} {symbol} — this requires your approval before it can proceed."
        message = AgentMessage(session_id=session.id, role="assistant", content=content, tool_calls=None, citations=None)
        db.add(message)
        await db.flush()
        await db.refresh(message)

        yield StreamEvent(
            "interrupt",
            {
                "trade_approval_id": interrupted_payload.get("trade_approval_id"),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
            },
        )
        yield StreamEvent("done", {"message_id": str(message.id)})
        return

    for tr in latest_tool_results:
        yield StreamEvent("tool_call", {"name": tr.get("name"), "args": tr.get("args", {}), "result": tr.get("result")})
    for c in latest_citations:
        yield StreamEvent("citation", c)

    words = latest_draft.split(" ") if latest_draft else []
    for i in range(0, len(words), _TOKEN_CHUNK_WORDS):
        piece = " ".join(words[i : i + _TOKEN_CHUNK_WORDS])
        if i + _TOKEN_CHUNK_WORDS < len(words):
            piece += " "
        yield StreamEvent("token", {"text": piece})

    message = AgentMessage(
        session_id=session.id,
        role="assistant",
        content=latest_draft,
        tool_calls=latest_tool_results or None,
        citations=latest_citations or None,
    )
    db.add(message)
    await db.flush()
    await db.refresh(message)
    yield StreamEvent("done", {"message_id": str(message.id)})


async def send_message(
    db: AsyncSession, session_id: str, user_id: str, content: str, checkpointer: BaseCheckpointSaver
) -> AsyncIterator[StreamEvent]:
    session = await _get_owned_session(db, session_id, user_id)

    user_message = AgentMessage(session_id=session.id, role="user", content=content)
    db.add(user_message)
    await db.flush()

    portfolio_id = str(session.portfolio_id) if session.portfolio_id else None
    tools = {t.name: t for t in build_tools(db, user_id, portfolio_id)}
    graph = build_graph(checkpointer)
    config = _thread_config(str(session.id), tools, db)

    initial_state = {
        "messages": [HumanMessage(content)],
        "session_id": str(session.id),
        "user_id": user_id,
        "portfolio_id": portfolio_id,
    }
    async for event in _persist_and_stream(db, session, graph, config, initial_state):
        yield event


async def resume_session(
    db: AsyncSession, session_id: str, user_id: str, checkpointer: BaseCheckpointSaver
) -> AsyncIterator[StreamEvent]:
    """Resumes an interrupted graph after a trade decision has been
    recorded (see `app/api/v1/trade_approvals.py::decide_trade_approval`).
    Builds the resume payload from the most recently created
    `trade_approvals` row for this session — the decision endpoint always
    flushes its status change before calling this, so the row this reads is
    already up to date.

    Safe to call even if there is nothing pending: if the checkpointed
    graph has no interrupted task (`state.next` is empty — e.g. it was
    already resumed once), this returns a `done` event referencing the
    latest persisted message instead of erroring."""
    session = await _get_owned_session(db, session_id, user_id)
    portfolio_id = str(session.portfolio_id) if session.portfolio_id else None
    tools = {t.name: t for t in build_tools(db, user_id, portfolio_id)}
    graph = build_graph(checkpointer)
    config = _thread_config(str(session.id), tools, db)

    state = await graph.aget_state(config)
    if not state.next:
        result = await db.execute(
            select(AgentMessage).where(AgentMessage.session_id == session.id).order_by(AgentMessage.created_at.desc())
        )
        last = result.scalars().first()
        yield StreamEvent("done", {"message_id": str(last.id) if last else ""})
        return

    result = await db.execute(
        select(TradeApproval).where(TradeApproval.session_id == session.id).order_by(TradeApproval.created_at.desc())
    )
    approval = result.scalars().first()
    if approval is None:
        yield StreamEvent("done", {"message_id": ""})
        return

    decision_payload = {
        "status": approval.status,
        "symbol": approval.symbol,
        "side": approval.side,
        "quantity": float(approval.quantity),
        "broker_order_id": approval.broker_order_id,
        "note": (approval.risk_checks or {}).get("decision_note"),
    }
    async for event in _persist_and_stream(db, session, graph, config, Command(resume=decision_payload)):
        yield event
