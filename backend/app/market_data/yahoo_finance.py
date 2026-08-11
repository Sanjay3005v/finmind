"""Real market data via Yahoo Finance's public (keyless) chart endpoint.

No API key is configured for this project, so this is the pragmatic real
data source: `query1.finance.yahoo.com/v8/finance/chart/{ticker}` returns a
real, live quote (`meta.regularMarketPrice`) and a real historical OHLC
series for any ticker Yahoo covers — including NSE equities (`.NS` suffix)
and, for gold/silver, real INR-denominated NSE-listed ETFs that track the
domestic metal price (GOLDBEES, SILVERBEES) since Yahoo has no MCX spot feed.
This module NEVER fabricates a price — any failure raises `AppError` rather
than returning a guessed/interpolated value.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog

from app.core.errors import AppError

logger = structlog.get_logger(__name__)

_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
# Yahoo's endpoint 403s a default httpx/requests user agent; a plain browser
# UA is enough to pass, no auth/cookies required for the chart endpoint.
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FinmindBot/1.0)"}
_TIMEOUT = 10.0

# Real, tradable, INR-denominated NSE ETFs standing in for domestic gold/
# silver spot prices — Yahoo Finance has no MCX feed. Documented explicitly
# so this mapping is auditable, not a silent guess.
_COMMODITY_PROXY_TICKERS = {
    "GOLD": "GOLDBEES.NS",
    "SILVER": "SILVERBEES.NS",
}

_EXCHANGE_SUFFIX = {
    "NSE": ".NS",
    "BSE": ".BO",
}


def to_yahoo_ticker(symbol: str, exchange: str) -> str:
    symbol_upper = symbol.upper()
    if symbol_upper in _COMMODITY_PROXY_TICKERS:
        return _COMMODITY_PROXY_TICKERS[symbol_upper]
    suffix = _EXCHANGE_SUFFIX.get(exchange.upper(), "")
    return f"{symbol_upper}{suffix}"


@dataclass
class Quote:
    symbol: str
    exchange: str
    ticker: str
    price: float
    currency: str
    as_of: datetime


@dataclass
class PricePoint:
    date: str  # ISO 8601
    close: float
    # OHLCV — present whenever Yahoo's quote block has them (it usually
    # does for daily bars); None rather than a guessed value when it doesn't.
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None


_RATE_LIMIT_RETRIES = 3
_RATE_LIMIT_BACKOFF_SECONDS = 1.5


async def _fetch_chart(ticker: str, range_: str, interval: str) -> dict:
    response: Optional[httpx.Response] = None
    for attempt in range(_RATE_LIMIT_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(
                    _CHART_URL.format(ticker=ticker),
                    params={"range": range_, "interval": interval},
                    headers=_HEADERS,
                )
        except httpx.HTTPError as exc:
            raise AppError(
                code="MARKET_DATA_UNAVAILABLE", message=f"Could not reach the market data provider: {exc}", status_code=502
            ) from exc

        # Yahoo's keyless endpoint rate-limits per source IP in short bursts
        # (seen in practice from Render's shared IPs) — this is usually gone
        # within a couple seconds, so a brief retry recovers it rather than
        # failing a refresh outright on a transient throttle.
        if response.status_code == 429 and attempt < _RATE_LIMIT_RETRIES:
            logger.warning("market_data_rate_limited_retrying", ticker=ticker, attempt=attempt + 1)
            # Jittered so concurrent multi-symbol refreshes (get_quotes fires
            # them all at once) don't retry in lockstep and re-trigger the
            # same burst limit together.
            delay = _RATE_LIMIT_BACKOFF_SECONDS * (attempt + 1) + random.uniform(0, 1.0)
            await asyncio.sleep(delay)
            continue
        break

    assert response is not None
    if response.status_code == 404:
        raise AppError(code="SYMBOL_NOT_FOUND", message=f"No market data found for '{ticker}'.", status_code=404)
    if response.status_code != 200:
        raise AppError(
            code="MARKET_DATA_UNAVAILABLE",
            message=f"Market data provider returned HTTP {response.status_code} for '{ticker}'.",
            status_code=502,
        )

    payload = response.json()
    results = payload.get("chart", {}).get("result")
    if not results:
        error = payload.get("chart", {}).get("error") or {}
        raise AppError(
            code="SYMBOL_NOT_FOUND",
            message=error.get("description") or f"No market data found for '{ticker}'.",
            status_code=404,
        )
    return results[0]


async def get_quote(symbol: str, exchange: str = "NSE") -> Quote:
    ticker = to_yahoo_ticker(symbol, exchange)
    result = await _fetch_chart(ticker, range_="1d", interval="1d")
    meta = result.get("meta", {})
    price = meta.get("regularMarketPrice")
    if price is None:
        raise AppError(code="SYMBOL_NOT_FOUND", message=f"No live price available for '{ticker}'.", status_code=404)
    return Quote(
        symbol=symbol.upper(),
        exchange=exchange.upper(),
        ticker=ticker,
        price=float(price),
        currency=meta.get("currency") or "INR",
        as_of=datetime.now(timezone.utc),
    )


async def get_quotes(items: list[tuple[str, str]]) -> tuple[list[Quote], list[dict]]:
    """Best-effort batch quote fetch — one symbol failing (delisted, typo,
    provider hiccup) never blocks the others. Returns `(quotes, failures)`
    where each failure is `{"symbol", "exchange", "error"}`."""

    async def _one(sym: str, exch: str) -> tuple[Optional[Quote], Optional[dict]]:
        try:
            return await get_quote(sym, exch), None
        except AppError as exc:
            logger.warning("market_data_quote_failed", symbol=sym, exchange=exch, error=exc.message)
            return None, {"symbol": sym, "exchange": exch, "error": exc.message}

    results = await asyncio.gather(*(_one(sym, exch) for sym, exch in items))
    quotes = [q for q, _ in results if q is not None]
    failures = [f for _, f in results if f is not None]
    return quotes, failures


async def get_history(symbol: str, exchange: str = "NSE", range_: str = "1mo", interval: str = "1d") -> list[PricePoint]:
    ticker = to_yahoo_ticker(symbol, exchange)
    result = await _fetch_chart(ticker, range_=range_, interval=interval)

    timestamps = result.get("timestamp") or []
    quote_block = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote_block.get("close") or []
    opens = quote_block.get("open") or []
    highs = quote_block.get("high") or []
    lows = quote_block.get("low") or []
    volumes = quote_block.get("volume") or []

    def _at(series: list, i: int) -> Optional[float]:
        value = series[i] if i < len(series) else None
        return float(value) if value is not None else None

    points: list[PricePoint] = []
    for i, (ts, close) in enumerate(zip(timestamps, closes)):
        if close is None:
            continue
        points.append(
            PricePoint(
                date=datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                close=float(close),
                open=_at(opens, i),
                high=_at(highs, i),
                low=_at(lows, i),
                volume=_at(volumes, i),
            )
        )
    return points
