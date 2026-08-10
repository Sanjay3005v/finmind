from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TradeApprovalResponse(BaseModel):
    id: UUID
    session_id: Optional[UUID] = None
    user_id: UUID
    broker_connection_id: Optional[UUID] = None
    symbol: str
    exchange: str
    side: str
    quantity: float
    order_type: str
    limit_price: Optional[float] = None
    status: str
    requested_by: str
    reasoning: Optional[str] = None
    risk_checks: dict
    broker_order_id: Optional[str] = None
    created_at: datetime
    decided_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TradeDecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    note: Optional[str] = Field(default=None, max_length=1000)
