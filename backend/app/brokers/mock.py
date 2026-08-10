"""`MockAdapter` — deterministic paper-trading implementation of `BrokerAdapter`.

This is what every `mode='paper'` `broker_connections` row actually talks
to, regardless of the `broker` column (see `registry.get_adapter`). It never
makes a network call and never touches a real broker endpoint. `place_order`
always returns `is_paper=True` so nothing downstream can mistake a simulated
fill for a real one.
"""
from __future__ import annotations

import itertools
import uuid
from datetime import datetime, timezone

from app.brokers.base import BrokerAdapter
from app.brokers.schemas import (
    AuthResult,
    FundsDTO,
    HoldingDTO,
    OrderRequest,
    OrderResult,
    PositionDTO,
    QuoteDTO,
)

# A handful of realistic NSE large-caps with plausible (illustrative, not
# live) prices — deterministic fixture data for demo/paper mode.
_FIXTURE_QUOTES: dict[str, float] = {
    "RELIANCE": 2945.60,
    "TCS": 4128.15,
    "INFY": 1845.90,
    "HDFCBANK": 1687.25,
}

_FIXTURE_HOLDINGS: list[HoldingDTO] = [
    HoldingDTO(symbol="RELIANCE", exchange="NSE", quantity=10, avg_price=2700.00,
               current_price=_FIXTURE_QUOTES["RELIANCE"], asset_class="equity", sector="Energy"),
    HoldingDTO(symbol="TCS", exchange="NSE", quantity=15, avg_price=3850.00,
               current_price=_FIXTURE_QUOTES["TCS"], asset_class="equity", sector="IT Services"),
    HoldingDTO(symbol="INFY", exchange="NSE", quantity=20, avg_price=1600.00,
               current_price=_FIXTURE_QUOTES["INFY"], asset_class="equity", sector="IT Services"),
    HoldingDTO(symbol="HDFCBANK", exchange="NSE", quantity=12, avg_price=1550.00,
               current_price=_FIXTURE_QUOTES["HDFCBANK"], asset_class="equity", sector="Financial Services"),
]

_DEMO_CASH_BALANCE = 500_000.00


class MockAdapter(BrokerAdapter):
    """Deterministic fixture adapter. Safe to instantiate with no
    credentials at all — paper trading never needs a real broker session."""

    def __init__(self, broker_label: str | None = None) -> None:
        # `broker_label` is only kept for logging/debugging context (which
        # real broker this paper connection will map to later); it never
        # changes behavior.
        self.broker_label = broker_label or "mock"
        self._order_counter = itertools.count(1)
        self._orders: dict[str, OrderResult] = {}

    async def authenticate(self, credentials: dict) -> AuthResult:
        return AuthResult(
            success=True,
            session_token=f"paper-session-{uuid.uuid4().hex[:12]}",
            message="Paper trading mode — no real broker authentication performed.",
        )

    async def get_holdings(self) -> list[HoldingDTO]:
        return [h.model_copy() for h in _FIXTURE_HOLDINGS]

    async def get_positions(self) -> list[PositionDTO]:
        # No open intraday positions in the paper fixture by default.
        return []

    async def get_funds(self) -> FundsDTO:
        return FundsDTO(
            available_cash=_DEMO_CASH_BALANCE,
            used_margin=0.0,
            total_balance=_DEMO_CASH_BALANCE,
            currency="INR",
        )

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> QuoteDTO:
        price = _FIXTURE_QUOTES.get(symbol.upper())
        if price is None:
            # Deterministic fallback so any symbol is quotable in demo mode,
            # without pretending to know a real market price.
            price = 100.0 + (sum(ord(c) for c in symbol.upper()) % 900)
        return QuoteDTO(
            symbol=symbol.upper(),
            exchange=exchange,
            last_price=price,
            open=price,
            high=price,
            low=price,
            close=price,
            volume=0,
            timestamp=datetime.now(timezone.utc),
        )

    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Simulates an immediate fill at the last known/mock quote. NEVER
        calls a real broker endpoint — this is the paper-mode safety
        boundary required by the trade-execution authorization model."""
        quote = await self.get_quote(order.symbol, order.exchange)
        fill_price = order.limit_price if order.order_type == "limit" and order.limit_price else quote.last_price
        broker_order_id = f"PAPER-{next(self._order_counter):06d}-{uuid.uuid4().hex[:6]}"
        result = OrderResult(
            broker_order_id=broker_order_id,
            status="filled",
            symbol=order.symbol.upper(),
            exchange=order.exchange,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            is_paper=True,
            message="Simulated fill (paper trading) — no real order was placed.",
            timestamp=datetime.now(timezone.utc),
        )
        self._orders[broker_order_id] = result
        return result

    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        cached = self._orders.get(broker_order_id)
        if cached is not None:
            return cached
        return OrderResult(
            broker_order_id=broker_order_id,
            status="rejected",
            symbol="",
            side="buy",
            quantity=0,
            is_paper=True,
            message="Unknown paper order id.",
            timestamp=datetime.now(timezone.utc),
        )

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        cached = self._orders.get(broker_order_id)
        if cached is None:
            return OrderResult(
                broker_order_id=broker_order_id,
                status="rejected",
                symbol="",
                side="buy",
                quantity=0,
                is_paper=True,
                message="Unknown paper order id — nothing to cancel.",
                timestamp=datetime.now(timezone.utc),
            )
        # Paper fills are immediate, so by the time a cancel request could
        # arrive the simulated order is already filled — mirrors real
        # broker behavior where a filled order can't be cancelled.
        cancelled = cached.model_copy(update={"message": "Already filled (paper trading) — cannot cancel."})
        return cancelled
