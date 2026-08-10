"""FYERS API v3 adapter.

Reference (to the best of the author's knowledge, FYERS API v3 —
myapi.fyers.in docs): OAuth2-like authorization-code flow with an
`appIdHash` (SHA-256 of `"{client_id}:{secret_key}"`) instead of a plain
client secret in the token-exchange body. Like Upstox, the
authorize-redirect half of this flow is a callback-driven step out of scope
for this phase; `authenticate` here assumes an authorization `code` (or an
already-issued `access_token`) is present in `credentials`.

Base URL: https://api-t1.fyers.in/api/v3
Authorize: GET  https://api-t1.fyers.in/api/v3/generate-authcode
Token:     POST https://api-t1.fyers.in/api/v3/validate-authcode
           body: {grant_type: "authorization_code", appIdHash, code}
Auth header on secure calls: `Authorization: <client_id>:<access_token>`
(FYERS concatenates client_id and token with a colon rather than a Bearer
prefix — verified against the general shape of FYERS v3 docs, but flagged
per rule below in case of a version-specific change.)

Endpoints used below:
  - GET    /api/v3/holdings
  - GET    /api/v3/positions
  - GET    /api/v3/funds
  - GET    /api/v3/data/quotes
  - POST   /api/v3/orders/sync
  - GET    /api/v3/orders
  - DELETE /api/v3/orders

# TODO: verify against live docs — FYERS symbol format is
# `EXCHANGE:SYMBOL-EQ` (e.g. "NSE:SBIN-EQ"); this adapter builds that string
# from `symbol`/`exchange` but has not been checked against a live response
# for every field name below (esp. `orders/sync` vs a plain `/orders` POST,
# which FYERS has changed across API versions).
"""
from __future__ import annotations

import hashlib
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

BASE_URL = "https://api-t1.fyers.in/api/v3"


def _fyers_symbol(symbol: str, exchange: str) -> str:
    return f"{exchange}:{symbol.upper()}-EQ"


class FyersAdapter(BrokerAdapter):
    def __init__(self, credentials: Optional[dict] = None, client: Optional[httpx.AsyncClient] = None):
        settings = get_settings()
        credentials = credentials or {}
        self.client_id = credentials.get("client_id") or settings.FYERS_CLIENT_ID
        self.secret_key = credentials.get("secret_key") or settings.FYERS_SECRET_KEY
        self.redirect_uri = credentials.get("redirect_uri") or settings.FYERS_REDIRECT_URI
        self.access_token: Optional[str] = credentials.get("access_token")
        self._client = client

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.access_token and self.client_id:
            headers["Authorization"] = f"{self.client_id}:{self.access_token}"
        return headers

    def _http(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(base_url=BASE_URL, headers=self._headers(), timeout=15.0)

    async def authenticate(self, credentials: dict) -> AuthResult:
        if credentials.get("access_token"):
            self.access_token = credentials["access_token"]
            return AuthResult(success=True, session_token=self.access_token)
        code = credentials.get("code")
        if not code:
            return AuthResult(success=False, message="Missing FYERS authorization code.")
        app_id_hash = hashlib.sha256(f"{self.client_id}:{self.secret_key}".encode("utf-8")).hexdigest()
        async with self._http() as client:
            resp = await client.post(
                "/validate-authcode",
                json={"grant_type": "authorization_code", "appIdHash": app_id_hash, "code": code},
            )
        if resp.status_code != 200:
            return AuthResult(success=False, message=f"FYERS token exchange failed: {resp.status_code}")
        data = resp.json()
        self.access_token = data.get("access_token")
        if not self.access_token:
            return AuthResult(success=False, message="FYERS token exchange did not return access_token.")
        return AuthResult(success=True, session_token=self.access_token)

    async def get_holdings(self) -> list[HoldingDTO]:
        async with self._http() as client:
            resp = await client.get("/holdings")
        resp.raise_for_status()
        data = resp.json().get("holdings", []) or []
        # TODO: verify against live docs — symbol/exchange/qty/costPrice/ltp
        # field names are to the best of my knowledge for FYERS v3 holdings.
        return [
            HoldingDTO(
                symbol=str(item.get("symbol", "")).split(":")[-1].replace("-EQ", ""),
                exchange=item.get("exchange", "NSE"),
                quantity=float(item.get("qty", 0)),
                avg_price=float(item.get("costPrice", 0)),
                current_price=float(item["ltp"]) if item.get("ltp") is not None else None,
            )
            for item in data
        ]

    async def get_positions(self) -> list[PositionDTO]:
        async with self._http() as client:
            resp = await client.get("/positions")
        resp.raise_for_status()
        data = resp.json().get("netPositions", []) or []
        return [
            PositionDTO(
                symbol=str(item.get("symbol", "")).split(":")[-1].replace("-EQ", ""),
                exchange=item.get("exchange", "NSE"),
                side="buy" if float(item.get("netQty", 0)) >= 0 else "sell",
                quantity=abs(float(item.get("netQty", 0))),
                avg_price=float(item.get("avgPrice", 0)),
                current_price=float(item["ltp"]) if item.get("ltp") is not None else None,
                product_type=item.get("productType"),
            )
            for item in data
        ]

    async def get_funds(self) -> FundsDTO:
        async with self._http() as client:
            resp = await client.get("/funds")
        resp.raise_for_status()
        data = resp.json().get("fund_limit", []) or []
        # TODO: verify against live docs — FYERS returns a list of named
        # buckets (e.g. "Available Balance", "Utilized Amount"); matching by
        # title string is brittle and unverified against a live response.
        available = next((float(b.get("equityAmount", 0)) for b in data if b.get("title") == "Available Balance"), 0.0)
        used = next((float(b.get("equityAmount", 0)) for b in data if b.get("title") == "Utilized Amount"), 0.0)
        return FundsDTO(available_cash=available, used_margin=used, total_balance=available + used)

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> QuoteDTO:
        fy_symbol = _fyers_symbol(symbol, exchange)
        async with self._http() as client:
            resp = await client.get("/data/quotes", params={"symbols": fy_symbol})
        resp.raise_for_status()
        payload = resp.json().get("d", []) or []
        item = payload[0].get("v", {}) if payload else {}
        return QuoteDTO(
            symbol=symbol.upper(),
            exchange=exchange,
            last_price=float(item.get("lp", 0)),
            open=float(item["open_price"]) if item.get("open_price") is not None else None,
            high=float(item["high_price"]) if item.get("high_price") is not None else None,
            low=float(item["low_price"]) if item.get("low_price") is not None else None,
            close=float(item["prev_close_price"]) if item.get("prev_close_price") is not None else None,
            timestamp=datetime.now(timezone.utc),
        )

    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Real FYERS order placement. Only ever called on a `mode='live'`
        adapter — not wired to any API route yet."""
        # TODO: verify against live docs — `/orders/sync` vs `/orders` for
        # placement has changed across FYERS API versions; body shape
        # (symbol, qty, type, side, productType, limitPrice, stopPrice,
        # validity, disclosedQty, offlineOrder) is to the best of my
        # knowledge for FYERS v3.
        body = {
            "symbol": _fyers_symbol(order.symbol, order.exchange),
            "qty": int(order.quantity),
            "type": 1 if order.order_type == "limit" else 2,  # 1=Limit, 2=Market
            "side": 1 if order.side == "buy" else -1,
            "productType": "CNC" if order.product_type == "delivery" else "INTRADAY",
            "limitPrice": order.limit_price or 0,
            "stopPrice": 0,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False,
        }
        async with self._http() as client:
            resp = await client.post("/orders/sync", json=body)
        resp.raise_for_status()
        data = resp.json()
        return OrderResult(
            broker_order_id=str(data.get("id", "")),
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
            resp = await client.get("/orders", params={"id": broker_order_id})
        resp.raise_for_status()
        data = resp.json().get("orderBook", []) or []
        item = data[0] if data else {}
        return OrderResult(
            broker_order_id=broker_order_id,
            status=str(item.get("status", "pending")),
            symbol=str(item.get("symbol", "")).split(":")[-1].replace("-EQ", ""),
            exchange=item.get("exchange", "NSE"),
            side="buy" if item.get("side") == 1 else "sell",
            quantity=float(item.get("qty", 0)),
            price=float(item.get("limitPrice", 0)) or None,
            is_paper=False,
        )

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        async with self._http() as client:
            resp = await client.request("DELETE", "/orders", json={"id": broker_order_id})
        resp.raise_for_status()
        return await self.get_order_status(broker_order_id)
