"""Broker connection management: connect (paper by default), list, sync,
disconnect. Live-order placement/trade-approval wiring is out of scope for
this phase — see `app/brokers/base.py` and `app/services/broker_service.py`.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_owned_broker_connection, parse_user_uuid
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.broker_connection import BrokerConnection
from app.schemas.broker_connection import (
    BrokerConnectionCreateRequest,
    BrokerConnectionResponse,
    BrokerConnectionSyncResponse,
)
from app.services import broker_service

router = APIRouter(
    prefix="/broker-connections", tags=["broker-connections"], dependencies=[Depends(rate_limit_dependency)]
)


@router.get("", response_model=list[BrokerConnectionResponse])
async def list_broker_connections(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[BrokerConnection]:
    owner_uuid = parse_user_uuid(user_id)
    return await broker_service.list_connections(db, owner_uuid)


@router.post("", response_model=BrokerConnectionResponse, status_code=201)
async def create_broker_connection(
    payload: BrokerConnectionCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> BrokerConnection:
    owner_uuid = parse_user_uuid(user_id)
    return await broker_service.create_connection(
        db,
        owner_uuid,
        broker=payload.broker,
        mode=payload.mode,
        credentials=payload.credentials,
        label=payload.label,
    )


@router.post("/{id}/sync", response_model=BrokerConnectionSyncResponse)
async def sync_broker_connection(
    connection: BrokerConnection = Depends(get_owned_broker_connection),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> BrokerConnectionSyncResponse:
    # NOTE: runs synchronously for now. This becomes a Celery background
    # task (`app/workers/tasks.py`) in a later phase, returning a job id
    # instead of blocking the request per API_CONTRACTS.md's eventual shape.
    owner_uuid = parse_user_uuid(user_id)
    updated_connection, holdings_synced = await broker_service.sync_holdings(db, connection.id, owner_uuid)
    return BrokerConnectionSyncResponse(
        connection_id=updated_connection.id,
        holdings_synced=holdings_synced,
        last_synced_at=updated_connection.last_synced_at,
    )


@router.delete("/{id}", status_code=204)
async def delete_broker_connection(
    connection: BrokerConnection = Depends(get_owned_broker_connection),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    owner_uuid = parse_user_uuid(user_id)
    await broker_service.disconnect(db, connection.id, owner_uuid)
