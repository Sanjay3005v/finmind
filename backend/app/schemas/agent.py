from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    portfolio_id: Optional[UUID] = None
    title: Optional[str] = Field(default=None, max_length=200)


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    portfolio_id: Optional[UUID] = None
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    tool_calls: Optional[list | dict] = None
    citations: Optional[list | dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
