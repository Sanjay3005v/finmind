"""Unit tests for app/market_data/yahoo_finance.py — httpx mocked via
monkeypatch so the suite never depends on the real network."""
from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.market_data import get_history, get_quote, get_quotes
from app.market_data import yahoo_finance


def _chart_payload(price=100.0, currency="INR", timestamps=None, closes=None, opens=None, highs=None, lows=None, volumes=None):
    quote_block = {"close": closes or []}
    if opens is not None:
        quote_block["open"] = opens
    if highs is not None:
        quote_block["high"] = highs
    if lows is not None:
        quote_block["low"] = lows
    if volumes is not None:
        quote_block["volume"] = volumes
    return {
        "chart": {
            "result": [
                {
                    "meta": {"regularMarketPrice": price, "currency": currency},
                    "timestamp": timestamps or [],
                    "indicators": {"quote": [quote_block]},
                }
            ],
            "error": None,
        }
    }


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


async def _no_op_sleep(*_args, **_kwargs) -> None:
    return None


def _patch_get(monkeypatch, response_by_ticker):
    async def _fake_get(self, url, params=None, headers=None):
        ticker = url.rsplit("/", 1)[-1]
        return response_by_ticker[ticker]

    monkeypatch.setattr("httpx.AsyncClient.get", _fake_get)


@pytest.mark.asyncio
async def test_get_quote_retries_on_429_then_succeeds(monkeypatch):
    monkeypatch.setattr(yahoo_finance.asyncio, "sleep", _no_op_sleep)  # skip real backoff delay
    calls = {"count": 0}

    async def _fake_get(self, url, params=None, headers=None):
        calls["count"] += 1
        if calls["count"] < 3:
            return _FakeResponse(429, {})
        return _FakeResponse(200, _chart_payload(price=500.0))

    monkeypatch.setattr("httpx.AsyncClient.get", _fake_get)
    quote = await get_quote("RELIANCE", "NSE")
    assert quote.price == 500.0
    assert calls["count"] == 3


@pytest.mark.asyncio
async def test_get_quote_gives_up_after_max_retries_on_429(monkeypatch):
    monkeypatch.setattr(yahoo_finance.asyncio, "sleep", _no_op_sleep)
    _patch_get(monkeypatch, {"RELIANCE.NS": _FakeResponse(429, {})})
    with pytest.raises(AppError) as exc_info:
        await get_quote("RELIANCE", "NSE")
    assert exc_info.value.code == "MARKET_DATA_UNAVAILABLE"


def test_to_yahoo_ticker_maps_commodities_to_real_nse_etfs():
    assert yahoo_finance.to_yahoo_ticker("gold", "MCX") == "GOLDBEES.NS"
    assert yahoo_finance.to_yahoo_ticker("silver", "MCX") == "SILVERBEES.NS"
    assert yahoo_finance.to_yahoo_ticker("RELIANCE", "NSE") == "RELIANCE.NS"
    assert yahoo_finance.to_yahoo_ticker("SBIN", "BSE") == "SBIN.BO"


@pytest.mark.asyncio
async def test_get_quote_returns_real_price(monkeypatch):
    _patch_get(monkeypatch, {"RELIANCE.NS": _FakeResponse(200, _chart_payload(price=1334.8))})
    quote = await get_quote("RELIANCE", "NSE")
    assert quote.price == 1334.8
    assert quote.ticker == "RELIANCE.NS"
    assert quote.currency == "INR"


@pytest.mark.asyncio
async def test_get_quote_raises_app_error_on_missing_symbol(monkeypatch):
    _patch_get(monkeypatch, {"FAKESYM.NS": _FakeResponse(404, {})})
    with pytest.raises(AppError) as exc_info:
        await get_quote("FAKESYM", "NSE")
    assert exc_info.value.code == "SYMBOL_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_quotes_isolates_individual_failures(monkeypatch):
    _patch_get(
        monkeypatch,
        {
            "TCS.NS": _FakeResponse(200, _chart_payload(price=2452.7)),
            "FAKESYM.NS": _FakeResponse(404, {}),
        },
    )
    quotes, failures = await get_quotes([("TCS", "NSE"), ("FAKESYM", "NSE")])
    assert len(quotes) == 1
    assert quotes[0].symbol == "TCS"
    assert len(failures) == 1
    assert failures[0]["symbol"] == "FAKESYM"


@pytest.mark.asyncio
async def test_get_history_skips_null_closes(monkeypatch):
    _patch_get(
        monkeypatch,
        {
            "RELIANCE.NS": _FakeResponse(
                200,
                _chart_payload(
                    timestamps=[1700000000, 1700086400, 1700172800],
                    closes=[100.0, None, 102.0],
                ),
            )
        },
    )
    points = await get_history("RELIANCE", "NSE", range_="1mo")
    assert len(points) == 2
    assert points[0].close == 100.0
    assert points[1].close == 102.0


@pytest.mark.asyncio
async def test_get_history_includes_ohlcv(monkeypatch):
    _patch_get(
        monkeypatch,
        {
            "RELIANCE.NS": _FakeResponse(
                200,
                _chart_payload(
                    timestamps=[1700000000, 1700086400],
                    closes=[100.0, 102.0],
                    opens=[98.0, 101.0],
                    highs=[101.0, 103.0],
                    lows=[97.0, 100.0],
                    volumes=[1200.0, 1500.0],
                ),
            )
        },
    )
    points = await get_history("RELIANCE", "NSE", range_="1mo")
    assert len(points) == 2
    assert points[0].open == 98.0
    assert points[0].high == 101.0
    assert points[0].low == 97.0
    assert points[0].volume == 1200.0
    assert points[1].close == 102.0


@pytest.mark.asyncio
async def test_get_history_ohlcv_defaults_to_none_when_absent(monkeypatch):
    _patch_get(
        monkeypatch,
        {
            "RELIANCE.NS": _FakeResponse(
                200,
                _chart_payload(timestamps=[1700000000], closes=[100.0]),
            )
        },
    )
    points = await get_history("RELIANCE", "NSE", range_="1mo")
    assert points[0].open is None
    assert points[0].high is None
    assert points[0].low is None
    assert points[0].volume is None
