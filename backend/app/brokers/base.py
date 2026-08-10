"""`BrokerAdapter` — the broker-agnostic contract every adapter implements.

`app/services/broker_service.py` and any future agent tool must only ever
call methods on this ABC (obtained via `app/brokers/registry.py`), never
import a concrete adapter directly — that is what keeps portfolio sync and
trade-approval logic broker-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.brokers.schemas import (
    AuthResult,
    FundsDTO,
    HoldingDTO,
    OrderRequest,
    OrderResult,
    PositionDTO,
    QuoteDTO,
)


class BrokerAdapter(ABC):
    """Every method is async because every real implementation makes a
    network call (httpx.AsyncClient). `MockAdapter` implements the same
    signatures synchronously-fast but stays `async def` for interface
    parity — callers never need to know which kind they're holding."""

    @abstractmethod
    async def authenticate(self, credentials: dict) -> AuthResult:
        """Establish/refresh a session against the broker using decrypted
        credentials. Must never be called with plaintext credentials that
        originated anywhere but in-memory decryption (see app/core/crypto.py)."""
        raise NotImplementedError

    @abstractmethod
    async def get_holdings(self) -> list[HoldingDTO]:
        raise NotImplementedError

    @abstractmethod
    async def get_positions(self) -> list[PositionDTO]:
        raise NotImplementedError

    @abstractmethod
    async def get_funds(self) -> FundsDTO:
        raise NotImplementedError

    @abstractmethod
    async def get_quote(self, symbol: str, exchange: str = "NSE") -> QuoteDTO:
        raise NotImplementedError

    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResult:
        """On a `paper`-mode connection this MUST be routed to `MockAdapter`
        by `registry.get_adapter` — a real adapter's `place_order` must never
        be reachable while `mode == 'paper'`. On a `live`-mode adapter this
        calls the broker's real order-placement endpoint; wiring a route
        that can actually invoke this (gated by `trade_approvals`) is out of
        scope for this phase."""
        raise NotImplementedError

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        raise NotImplementedError
