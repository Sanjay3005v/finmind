"""DhanHQ v2 REST API adapter.

Reference (to the best of the author's knowledge, DhanHQ API v2 —
docs.dhan.co): a long-lived per-user `access-token` generated from the Dhan
web/app, sent as a plain header — there is no OAuth authorization-code dance
like Upstox/FYERS.

Base URL: https://api.dhan.co/v2
Auth header: `access-token: <token>` (+ `Content-Type: application/json`)

Endpoints used below match the documented v2 surface:
  - GET  /v2/holdings
  - GET  /v2/positions
  - GET  /v2/fundlimit
  - POST /v2/orders                (place)
  - GET  /v2/orders/{order-id}     (status)
  - DELETE /v2/orders/{order-id}   (cancel)

# TODO: verify against live docs — DhanHQ identifies instruments by a
# numeric `securityId` (from Dhan's published scrip master CSV), not by
# plain trading symbol. This adapter does not implement symbol->securityId
# resolution (that requires downloading/caching Dhan's instrument master,
# out of scope for this phase), so `get_quote` and `place_order` below pass
# `symbol` through where Dhan actually expects `securityId` + `exchangeSegment`
# — do not treat the request bodies here as final without wiring that lookup.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog

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
from app.core.config import get_settings

logger = structlog.get_logger(__name__)

BASE_URL = "https://api.dhan.co/v2"


class DhanAdapter(BrokerAdapter):
    def __init__(self, credentials: Optional[dict] = None, client: Optional[httpx.AsyncClient] = None):
        settings = get_settings()
        credentials = credentials or {}
        self.client_id = credentials.get("client_id") or settings.DHAN_CLIENT_ID
        self.access_token = credentials.get("access_token") or settings.DHAN_ACCESS_TOKEN
        self._client = client

    def _headers(self) -> dict:
        return {"access-token": self.access_token or "", "Content-Type": "application/json"}

    def _http(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(base_url=BASE_URL, headers=self._headers(), timeout=15.0)

    async def authenticate(self, credentials: dict) -> AuthResult:
        # Dhan's access-token model has no separate login call — the token is
        # generated out-of-band on Dhan's site. "Authenticating" here just
        # means confirming the stored token is still accepted by a cheap
        # endpoint.
        self.access_token = credentials.get("access_token", self.access_token)
        self.client_id = credentials.get("client_id", self.client_id)
        if not self.access_token:
            return AuthResult(success=False, message="Missing Dhan access token.")
        async with self._http() as client:
            resp = await client.get("/fundlimit")
        if resp.status_code == 200:
            return AuthResult(success=True, session_token=self.access_token)
        return AuthResult(success=False, message=f"Dhan auth check failed: {resp.status_code}")

    async def get_holdings(self) -> list[HoldingDTO]:
        async with self._http() as client:
            resp = await client.get("/holdings")
        resp.raise_for_status()
        data = resp.json()
        # TODO: verify against live docs — field names below (tradingSymbol,
        # exchange, totalQty/availableQty, avgCostPrice, lastTradedPrice) are
        # to the best of my knowledge for the Dhan v2 holdings response.
        return [
            HoldingDTO(
                symbol=item.get("tradingSymbol", ""),
                exchange=item.get("exchange", "NSE"),
                quantity=float(item.get("totalQty", 0)),
                avg_price=float(item.get("avgCostPrice", 0)),
                current_price=float(item["lastTradedPrice"]) if item.get("lastTradedPrice") is not None else None,
            )
            for item in data or []
        ]

    async def get_positions(self) -> list[PositionDTO]:
        async with self._http() as client:
            resp = await client.get("/positions")
        resp.raise_for_status()
        data = resp.json()
        # TODO: verify against live docs — positionType/netQty/costPrice field
        # names are to the best of my knowledge for Dhan v2 positions.
        return [
            PositionDTO(
                symbol=item.get("tradingSymbol", ""),
                exchange=item.get("exchange", "NSE"),
                side="buy" if float(item.get("netQty", 0)) >= 0 else "sell",
                quantity=abs(float(item.get("netQty", 0))),
                avg_price=float(item.get("costPrice", 0)),
                current_price=float(item["lastTradedPrice"]) if item.get("lastTradedPrice") is not None else None,
                product_type=item.get("productType"),
            )
            for item in data or []
        ]

    async def get_funds(self) -> FundsDTO:
        async with self._http() as client:
            resp = await client.get("/fundlimit")
        resp.raise_for_status()
        data = resp.json()
        # TODO: verify against live docs — availabelBalance (sic, Dhan has a
        # documented typo in some versions)/sodLimit field names.
        available = float(data.get("availabelBalance", data.get("availableBalance", 0)))
        total = float(data.get("sodLimit", available))
        return FundsDTO(available_cash=available, used_margin=max(total - available, 0.0), total_balance=total)

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> QuoteDTO:
        # TODO: verify against live docs — Dhan's real-time quote endpoint is
        # `POST /v2/marketfeed/ltp` (or `/quote`/`/ohlc`) keyed by
        # `{exchangeSegment: [securityId, ...]}`, NOT plain trading symbol.
        # Without the symbol->securityId master mapping this call will not
        # work against the live API as written; not fabricating the exact
        # payload shape here beyond this best-effort attempt.
        async with self._http() as client:
            resp = await client.post(
                "/marketfeed/ltp",
                json={f"{exchange}_EQ": [symbol]},
            )
        resp.raise_for_status()
        data = resp.json()
        ltp = 0.0
        try:
            ltp = float(next(iter(data.get("data", {}).get(f"{exchange}_EQ", {}).values()))["last_price"])
        except (StopIteration, KeyError, TypeError, ValueError):
            logger.warning("dhan_quote_parse_fallback", symbol=symbol)
        return QuoteDTO(symbol=symbol.upper(), exchange=exchange, last_price=ltp, timestamp=datetime.now(timezone.utc))

    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Real Dhan order placement. Only ever called on a `mode='live'`
        adapter — never reachable from a `paper` connection (see
        `app/brokers/registry.py`). Not wired to any API route yet."""
        # TODO: verify against live docs — body shape (dhanClientId,
        # transactionType, exchangeSegment, productType, orderType, validity,
        # securityId, quantity, price) is to the best of my knowledge for
        # Dhan v2 `POST /orders`; `securityId` resolution from `order.symbol`
        # is NOT implemented (see module docstring).
        body = {
            "dhanClientId": self.client_id,
            "transactionType": "BUY" if order.side == "buy" else "SELL",
            "exchangeSegment": f"{order.exchange}_EQ",
            "productType": "CNC" if order.product_type == "delivery" else "INTRADAY",
            "orderType": "LIMIT" if order.order_type == "limit" else "MARKET",
            "validity": "DAY",
            "securityId": order.symbol,  # NOT a real securityId — see TODO above
            "quantity": int(order.quantity),
            "price": order.limit_price or 0,
        }
        async with self._http() as client:
            resp = await client.post("/orders", json=body)
        resp.raise_for_status()
        data = resp.json()
        return OrderResult(
            broker_order_id=str(data.get("orderId", "")),
            status=str(data.get("orderStatus", "pending")).lower(),
            symbol=order.symbol,
            exchange=order.exchange,
            side=order.side,
            quantity=order.quantity,
            price=order.limit_price,
            is_paper=False,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_order_status(self, broker_order_id: str) -> OrderResult:
        async with self._http() as client:
            resp = await client.get(f"/orders/{broker_order_id}")
        resp.raise_for_status()
        data = resp.json()
        return OrderResult(
            broker_order_id=broker_order_id,
            status=str(data.get("orderStatus", "pending")).lower(),
            symbol=data.get("tradingSymbol", ""),
            exchange=data.get("exchangeSegment", "NSE"),
            side="buy" if data.get("transactionType") == "BUY" else "sell",
            quantity=float(data.get("quantity", 0)),
            price=float(data.get("price", 0)) or None,
            is_paper=False,
        )

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        async with self._http() as client:
            resp = await client.delete(f"/orders/{broker_order_id}")
        resp.raise_for_status()
        return await self.get_order_status(broker_order_id)
