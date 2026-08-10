"""Upstox API v2 adapter.

Reference (to the best of the author's knowledge, Upstox API v2 —
upstox.com/developer/api-documentation): OAuth2 authorization-code flow.
The user is sent to an authorization dialog; Upstox redirects back to
`UPSTOX_REDIRECT_URI` with a `code`, which is exchanged for an access token.
That exchange step is a callback-driven flow (`/broker-connections/{id}/callback`
in API_CONTRACTS.md) that is out of scope for this phase — this adapter
implements `authenticate` assuming an authorization `code` is already in
`credentials`, and every data/order method assuming `access_token` is
already present.

Base URL: https://api.upstox.com/v2
Authorize: GET  https://api.upstox.com/v2/login/authorization/dialog
Token:     POST https://api.upstox.com/v2/login/authorization/token
           body (form-encoded): code, client_id, client_secret, redirect_uri,
           grant_type=authorization_code
Auth header on secure calls: `Authorization: Bearer <access_token>`

Endpoints used below:
  - GET    /v2/portfolio/long-term-holdings
  - GET    /v2/portfolio/short-term-positions
  - GET    /v2/user/get-funds-and-margin
  - GET    /v2/market-quote/quotes
  - POST   /v2/order/place
  - GET    /v2/order/details
  - DELETE /v2/order/cancel

# TODO: verify against live docs — Upstox identifies instruments by an
# `instrument_key` (e.g. "NSE_EQ|INE002A01018"), not a plain trading symbol.
# This adapter passes `EXCHANGE_EQ:SYMBOL`-shaped values where Upstox
# actually expects the ISIN-based instrument key (symbol->instrument_key
# resolution via Upstox's published instrument master is not implemented
# here, out of scope for this phase).
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

BASE_URL = "https://api.upstox.com/v2"


class UpstoxAdapter(BrokerAdapter):
    def __init__(self, credentials: Optional[dict] = None, client: Optional[httpx.AsyncClient] = None):
        settings = get_settings()
        credentials = credentials or {}
        self.api_key = credentials.get("api_key") or settings.UPSTOX_API_KEY
        self.api_secret = credentials.get("api_secret") or settings.UPSTOX_API_SECRET
        self.redirect_uri = credentials.get("redirect_uri") or settings.UPSTOX_REDIRECT_URI
        self.access_token: Optional[str] = credentials.get("access_token")
        self._client = client

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _http(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(base_url=BASE_URL, headers=self._headers(), timeout=15.0)

    async def authenticate(self, credentials: dict) -> AuthResult:
        code = credentials.get("code")
        if credentials.get("access_token"):
            self.access_token = credentials["access_token"]
            return AuthResult(success=True, session_token=self.access_token)
        if not code:
            return AuthResult(success=False, message="Missing Upstox authorization code.")
        async with self._http() as client:
            resp = await client.post(
                "/login/authorization/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "code": code,
                    "client_id": self.api_key,
                    "client_secret": self.api_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        if resp.status_code != 200:
            return AuthResult(success=False, message=f"Upstox token exchange failed: {resp.status_code}")
        data = resp.json()
        self.access_token = data.get("access_token")
        if not self.access_token:
            return AuthResult(success=False, message="Upstox token exchange did not return access_token.")
        return AuthResult(success=True, session_token=self.access_token, extra={"token_type": data.get("token_type")})

    async def get_holdings(self) -> list[HoldingDTO]:
        async with self._http() as client:
            resp = await client.get("/portfolio/long-term-holdings")
        resp.raise_for_status()
        data = resp.json().get("data", []) or []
        # TODO: verify against live docs — tradingsymbol/exchange/quantity/
        # average_price/last_price field names are to the best of my
        # knowledge for Upstox's long-term-holdings response.
        return [
            HoldingDTO(
                symbol=item.get("tradingsymbol", ""),
                exchange=item.get("exchange", "NSE"),
                quantity=float(item.get("quantity", 0)),
                avg_price=float(item.get("average_price", 0)),
                current_price=float(item["last_price"]) if item.get("last_price") is not None else None,
            )
            for item in data
        ]

    async def get_positions(self) -> list[PositionDTO]:
        async with self._http() as client:
            resp = await client.get("/portfolio/short-term-positions")
        resp.raise_for_status()
        data = resp.json().get("data", []) or []
        return [
            PositionDTO(
                symbol=item.get("tradingsymbol", ""),
                exchange=item.get("exchange", "NSE"),
                side="buy" if float(item.get("quantity", 0)) >= 0 else "sell",
                quantity=abs(float(item.get("quantity", 0))),
                avg_price=float(item.get("average_price", 0)),
                current_price=float(item["last_price"]) if item.get("last_price") is not None else None,
                product_type=item.get("product"),
            )
            for item in data
        ]

    async def get_funds(self) -> FundsDTO:
        async with self._http() as client:
            resp = await client.get("/user/get-funds-and-margin")
        resp.raise_for_status()
        data = resp.json().get("data", {}) or {}
        equity = data.get("equity", {}) if isinstance(data, dict) else {}
        # TODO: verify against live docs — available_margin/used_margin field
        # names under the `equity` segment key.
        available = float(equity.get("available_margin", 0))
        used = float(equity.get("used_margin", 0))
        return FundsDTO(available_cash=available, used_margin=used, total_balance=available + used)

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> QuoteDTO:
        # TODO: verify against live docs — should be keyed by `instrument_key`
        # (see module docstring), not `EXCHANGE:SYMBOL`.
        instrument = f"{exchange}_EQ:{symbol}"
        async with self._http() as client:
            resp = await client.get("/market-quote/quotes", params={"symbol": instrument})
        resp.raise_for_status()
        payload = resp.json().get("data", {}) or {}
        item = next(iter(payload.values()), {}) if payload else {}
        return QuoteDTO(
            symbol=symbol.upper(),
            exchange=exchange,
            last_price=float(item.get("last_price", 0)),
            timestamp=datetime.now(timezone.utc),
        )

    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Real Upstox order placement. Only ever called on a `mode='live'`
        adapter — not wired to any API route yet."""
        # TODO: verify against live docs — body shape (quantity, product,
        # validity, price, instrument_token, order_type, transaction_type,
        # disclosed_quantity, trigger_price, is_amo) is to the best of my
        # knowledge for Upstox's `POST /order/place`; `instrument_token`
        # resolution from `order.symbol` is not implemented.
        body = {
            "quantity": int(order.quantity),
            "product": "D" if order.product_type == "delivery" else "I",
            "validity": "DAY",
            "price": order.limit_price or 0,
            "instrument_token": f"{order.exchange}_EQ:{order.symbol}",  # NOT a real instrument_key — see TODO
            "order_type": "LIMIT" if order.order_type == "limit" else "MARKET",
            "transaction_type": "BUY" if order.side == "buy" else "SELL",
            "disclosed_quantity": 0,
            "trigger_price": 0,
            "is_amo": False,
        }
        async with self._http() as client:
            resp = await client.post("/order/place", json=body)
        resp.raise_for_status()
        data = resp.json().get("data", {}) or {}
        return OrderResult(
            broker_order_id=str(data.get("order_id", "")),
            status="pending",
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
            resp = await client.get("/order/details", params={"order_id": broker_order_id})
        resp.raise_for_status()
        data = resp.json().get("data", {}) or {}
        return OrderResult(
            broker_order_id=broker_order_id,
            status=str(data.get("status", "pending")).lower(),
            symbol=data.get("trading_symbol", ""),
            exchange=data.get("exchange", "NSE"),
            side="buy" if data.get("transaction_type") == "BUY" else "sell",
            quantity=float(data.get("quantity", 0)),
            price=float(data.get("price", 0)) or None,
            is_paper=False,
        )

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        async with self._http() as client:
            resp = await client.delete("/order/cancel", params={"order_id": broker_order_id})
        resp.raise_for_status()
        return await self.get_order_status(broker_order_id)
