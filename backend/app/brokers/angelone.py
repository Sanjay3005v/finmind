"""Angel One SmartAPI adapter.

Reference (to the best of the author's knowledge, SmartAPI —
smartapi.angelbroking.com docs): login is TOTP-based (username + password +
a 6-digit code derived from a TOTP secret configured once in the Angel One
app), not OAuth. A successful login returns a JWT (`jwtToken`) used as a
Bearer token on every subsequent "secure" call, alongside a fixed set of
`X-*` context headers SmartAPI requires on every request.

Base URL: https://apiconnect.angelbroking.com
Auth: POST /rest/auth/angelbroking/user/v1/loginByPassword
      body: {clientcode, password, totp}
      headers: X-PrivateKey (api key), X-UserType=USER, X-SourceID=WEB,
               X-ClientLocalIP, X-ClientPublicIP, X-MACAddress
      -> {data: {jwtToken, refreshToken, feedToken}}

Endpoints used below:
  - GET  /rest/secure/angelbroking/portfolio/v1/getHolding
  - GET  /rest/secure/angelbroking/portfolio/v1/getPosition
  - GET  /rest/secure/angelbroking/user/v1/getRMS
  - POST /rest/secure/angelbroking/order/v1/getLtpData
  - POST /rest/secure/angelbroking/order/v1/placeOrder
  - POST /rest/secure/angelbroking/order/v1/cancelOrder
  - GET  /rest/secure/angelbroking/order/v1/getOrderBook

# TODO: verify against live docs — SmartAPI's LTP/order endpoints expect a
# numeric `symboltoken` (from Angel One's published instrument master JSON)
# alongside `tradingsymbol`; this adapter passes only the trading symbol
# (symbol->token resolution is not implemented here, out of scope for this
# phase). Also verify the exact per-order status lookup path — Angel One's
# docs have moved this between `getOrderBook` (filter client-side by
# `orderid`) and a dedicated order-detail endpoint across API versions.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import struct
import time
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

BASE_URL = "https://apiconnect.angelbroking.com"


def _totp_now(secret: str, digits: int = 6, period: int = 30) -> str:
    """RFC 6238 TOTP, implemented directly (stdlib hmac/hashlib) rather than
    pulling in a TOTP library for one call site. Standard algorithm — not
    broker-specific, so no "verify against docs" flag needed here."""
    key = base64.b32decode(secret.upper().replace(" ", ""), casefold=True)
    counter = int(time.time() // period)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return str(code).zfill(digits)


class AngelOneAdapter(BrokerAdapter):
    def __init__(self, credentials: Optional[dict] = None, client: Optional[httpx.AsyncClient] = None):
        settings = get_settings()
        credentials = credentials or {}
        self.api_key = credentials.get("api_key") or settings.ANGELONE_API_KEY
        self.client_code = credentials.get("client_code") or settings.ANGELONE_CLIENT_CODE
        self.password = credentials.get("password") or settings.ANGELONE_PASSWORD
        self.totp_secret = credentials.get("totp_secret") or settings.ANGELONE_TOTP_SECRET
        self.jwt_token: Optional[str] = credentials.get("jwt_token")
        self._client = client

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-PrivateKey": self.api_key or "",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            # SmartAPI requires these but tolerates placeholder values from
            # server-side integrations that aren't a real end-user browser.
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            **({"Authorization": f"Bearer {self.jwt_token}"} if self.jwt_token else {}),
        }

    def _http(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(base_url=BASE_URL, headers=self._headers(), timeout=15.0)

    async def authenticate(self, credentials: dict) -> AuthResult:
        self.client_code = credentials.get("client_code", self.client_code)
        self.password = credentials.get("password", self.password)
        self.totp_secret = credentials.get("totp_secret", self.totp_secret)
        if not (self.client_code and self.password and self.totp_secret):
            return AuthResult(success=False, message="Missing Angel One client_code/password/totp_secret.")
        totp = _totp_now(self.totp_secret)
        async with self._http() as client:
            resp = await client.post(
                "/rest/auth/angelbroking/user/v1/loginByPassword",
                json={"clientcode": self.client_code, "password": self.password, "totp": totp},
            )
        if resp.status_code != 200:
            return AuthResult(success=False, message=f"Angel One login failed: {resp.status_code}")
        data = resp.json().get("data", {})
        self.jwt_token = data.get("jwtToken")
        if not self.jwt_token:
            return AuthResult(success=False, message="Angel One login did not return a jwtToken.")
        return AuthResult(
            success=True,
            session_token=self.jwt_token,
            extra={"refreshToken": data.get("refreshToken"), "feedToken": data.get("feedToken")},
        )

    async def get_holdings(self) -> list[HoldingDTO]:
        async with self._http() as client:
            resp = await client.get("/rest/secure/angelbroking/portfolio/v1/getHolding")
        resp.raise_for_status()
        data = resp.json().get("data", []) or []
        # TODO: verify against live docs — tradingsymbol/exchange/quantity/
        # averageprice/ltp field names are to the best of my knowledge for
        # SmartAPI's getHolding response.
        return [
            HoldingDTO(
                symbol=item.get("tradingsymbol", ""),
                exchange=item.get("exchange", "NSE"),
                quantity=float(item.get("quantity", 0)),
                avg_price=float(item.get("averageprice", 0)),
                current_price=float(item["ltp"]) if item.get("ltp") is not None else None,
            )
            for item in data
        ]

    async def get_positions(self) -> list[PositionDTO]:
        async with self._http() as client:
            resp = await client.get("/rest/secure/angelbroking/portfolio/v1/getPosition")
        resp.raise_for_status()
        data = resp.json().get("data", []) or []
        return [
            PositionDTO(
                symbol=item.get("tradingsymbol", ""),
                exchange=item.get("exchange", "NSE"),
                side="buy" if float(item.get("netqty", 0)) >= 0 else "sell",
                quantity=abs(float(item.get("netqty", 0))),
                avg_price=float(item.get("avgnetprice", 0)),
                current_price=float(item["ltp"]) if item.get("ltp") is not None else None,
                product_type=item.get("producttype"),
            )
            for item in data
        ]

    async def get_funds(self) -> FundsDTO:
        async with self._http() as client:
            resp = await client.get("/rest/secure/angelbroking/user/v1/getRMS")
        resp.raise_for_status()
        data = resp.json().get("data", {}) or {}
        # TODO: verify against live docs — availablecash/net field names.
        available = float(data.get("availablecash", 0))
        net = float(data.get("net", available))
        return FundsDTO(available_cash=available, used_margin=max(net - available, 0.0), total_balance=net)

    async def get_quote(self, symbol: str, exchange: str = "NSE") -> QuoteDTO:
        # TODO: verify against live docs — getLtpData requires `symboltoken`,
        # not just `tradingsymbol` (see module docstring); not implemented.
        async with self._http() as client:
            resp = await client.post(
                "/rest/secure/angelbroking/order/v1/getLtpData",
                json={"exchange": exchange, "tradingsymbol": symbol, "symboltoken": symbol},
            )
        resp.raise_for_status()
        data = resp.json().get("data", {}) or {}
        return QuoteDTO(
            symbol=symbol.upper(),
            exchange=exchange,
            last_price=float(data.get("ltp", 0)),
            open=float(data["open"]) if data.get("open") is not None else None,
            high=float(data["high"]) if data.get("high") is not None else None,
            low=float(data["low"]) if data.get("low") is not None else None,
            close=float(data["close"]) if data.get("close") is not None else None,
            timestamp=datetime.now(timezone.utc),
        )

    async def place_order(self, order: OrderRequest) -> OrderResult:
        """Real Angel One order placement. Only ever called on a
        `mode='live'` adapter — not wired to any API route yet."""
        # TODO: verify against live docs — body shape (variety, tradingsymbol,
        # symboltoken, transactiontype, exchange, ordertype, producttype,
        # duration, price, quantity) is to the best of my knowledge for
        # SmartAPI's placeOrder; `symboltoken` resolution is not implemented.
        body = {
            "variety": "NORMAL",
            "tradingsymbol": order.symbol,
            "symboltoken": order.symbol,  # NOT a real symboltoken — see TODO above
            "transactiontype": "BUY" if order.side == "buy" else "SELL",
            "exchange": order.exchange,
            "ordertype": "LIMIT" if order.order_type == "limit" else "MARKET",
            "producttype": "DELIVERY" if order.product_type == "delivery" else "INTRADAY",
            "duration": "DAY",
            "price": order.limit_price or 0,
            "quantity": order.quantity,
        }
        async with self._http() as client:
            resp = await client.post("/rest/secure/angelbroking/order/v1/placeOrder", json=body)
        resp.raise_for_status()
        data = resp.json().get("data", {}) or {}
        return OrderResult(
            broker_order_id=str(data.get("orderid", "")),
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
        # TODO: verify against live docs — using getOrderBook + client-side
        # filter by orderid; a dedicated order-detail endpoint may exist.
        async with self._http() as client:
            resp = await client.get("/rest/secure/angelbroking/order/v1/getOrderBook")
        resp.raise_for_status()
        orders = resp.json().get("data", []) or []
        match = next((o for o in orders if str(o.get("orderid")) == str(broker_order_id)), None)
        if match is None:
            return OrderResult(
                broker_order_id=broker_order_id, status="rejected", symbol="", side="buy", quantity=0, is_paper=False,
                message="Order id not found in order book.",
            )
        return OrderResult(
            broker_order_id=broker_order_id,
            status=str(match.get("status", "pending")).lower(),
            symbol=match.get("tradingsymbol", ""),
            exchange=match.get("exchange", "NSE"),
            side="buy" if match.get("transactiontype") == "BUY" else "sell",
            quantity=float(match.get("quantity", 0)),
            price=float(match.get("price", 0)) or None,
            is_paper=False,
        )

    async def cancel_order(self, broker_order_id: str) -> OrderResult:
        async with self._http() as client:
            resp = await client.post(
                "/rest/secure/angelbroking/order/v1/cancelOrder",
                json={"variety": "NORMAL", "orderid": broker_order_id},
            )
        resp.raise_for_status()
        return await self.get_order_status(broker_order_id)
