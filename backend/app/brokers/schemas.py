"""Broker-agnostic DTOs returned by every `BrokerAdapter` implementation.

Business logic (services, routers, agent tools) must only ever see these
shapes — never a raw broker API response — so nothing downstream branches
on which broker is actually configured.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AuthResult(BaseModel):
    success: bool
    session_token: Optional[str] = None
    message: Optional[str] = None
    # Raw, broker-specific extra fields (refresh token, feed token, expiry,
    # etc.) an adapter may need to keep around for subsequent calls. Never
    # logged; callers must treat this as sensitive.
    extra: dict = Field(default_factory=dict)


class HoldingDTO(BaseModel):
    symbol: str
    exchange: str = "NSE"
    quantity: float
    avg_price: float
    current_price: Optional[float] = None
    asset_class: str = "equity"
    sector: Optional[str] = None
    currency: str = "INR"


class PositionDTO(BaseModel):
    symbol: str
    exchange: str = "NSE"
    side: str  # "buy" | "sell" (net direction of the open position)
    quantity: float
    avg_price: float
    current_price: Optional[float] = None
    pnl: Optional[float] = None
    product_type: Optional[str] = None  # e.g. intraday / delivery / margin


class FundsDTO(BaseModel):
    available_cash: float
    used_margin: float = 0.0
    total_balance: float
    currency: str = "INR"


class QuoteDTO(BaseModel):
    symbol: str
    exchange: str = "NSE"
    last_price: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    timestamp: Optional[datetime] = None


class OrderRequest(BaseModel):
    symbol: str
    exchange: str = "NSE"
    side: str  # "buy" | "sell"
    quantity: float
    order_type: str = "market"  # "market" | "limit"
    limit_price: Optional[float] = None
    product_type: str = "delivery"  # broker-specific label (delivery/intraday/margin)


class OrderResult(BaseModel):
    broker_order_id: str
    status: str  # "filled" | "pending" | "rejected" | "cancelled"
    symbol: str
    exchange: str = "NSE"
    side: str
    quantity: float
    price: Optional[float] = None
    is_paper: bool = False
    message: Optional[str] = None
    timestamp: Optional[datetime] = None
