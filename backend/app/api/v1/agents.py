"""Agent sessions + streaming chat (docs/API_CONTRACTS.md "Agents" section).

`POST /agents/sessions/{id}/messages` and `POST /agents/sessions/{id}/resume`
return a real SSE stream (`text/event-stream`), each event formatted exactly
as `event: <name>\\ndata: <json>\\n\\n` per the streaming event contract at
the bottom of API_CONTRACTS.md.
"""
from __future__ import annotations

import json
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.base import BaseCheckpointSaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.checkpoint import get_checkpointer
from app.api.v1.deps import get_owned_agent_session
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.agent_session import AgentSession
from app.schemas.agent import MessageResponse, SendMessageRequest, SessionCreateRequest, SessionResponse
from app.services import agent_service

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(rate_limit_dependency)])


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


async def _sse_stream(events: AsyncIterator[agent_service.StreamEvent]) -> AsyncIterator[str]:
    async for evt in events:
        yield _format_sse(evt.event, evt.data)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[AgentSession]:
    return await agent_service.list_sessions(db, user_id)


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    payload: SessionCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> AgentSession:
    return await agent_service.create_session(
        db,
        user_id,
        portfolio_id=str(payload.portfolio_id) if payload.portfolio_id else None,
        title=payload.title,
    )


@router.get("/sessions/{id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session: AgentSession = Depends(get_owned_agent_session),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    return await agent_service.get_messages(db, str(session.id), user_id)


@router.post("/sessions/{id}/messages")
async def send_message(
    payload: SendMessageRequest,
    session: AgentSession = Depends(get_owned_agent_session),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
) -> StreamingResponse:
    events = agent_service.send_message(db, str(session.id), user_id, payload.content, checkpointer)
    return StreamingResponse(_sse_stream(events), media_type="text/event-stream")


@router.post("/sessions/{id}/resume")
async def resume_session(
    session: AgentSession = Depends(get_owned_agent_session),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
    checkpointer: BaseCheckpointSaver = Depends(get_checkpointer),
) -> StreamingResponse:
    events = agent_service.resume_session(db, str(session.id), user_id, checkpointer)
    return StreamingResponse(_sse_stream(events), media_type="text/event-stream")
