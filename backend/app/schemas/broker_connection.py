from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.broker_connection import BROKERS, MODES


class BrokerConnectionCreateRequest(BaseModel):
    broker: str
    mode: Optional[str] = None  # defaults to "paper" in the service layer
    credentials: Optional[dict] = None
    label: Optional[str] = Field(default=None, max_length=200)

    @field_validator("broker")
    @classmethod
    def _validate_broker(cls, v: str) -> str:
        if v not in BROKERS:
            raise ValueError(f"broker must be one of {BROKERS}")
        return v

    @field_validator("mode")
    @classmethod
    def _validate_mode(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        return v


class BrokerConnectionResponse(BaseModel):
    """Never includes `encrypted_credentials` — credentials are write-only
    from the API's perspective."""

    id: UUID
    user_id: UUID
    broker: str
    mode: str
    status: str
    label: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrokerConnectionSyncResponse(BaseModel):
    connection_id: UUID
    holdings_synced: int
    last_synced_at: Optional[datetime] = None
