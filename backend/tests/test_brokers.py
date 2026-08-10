"""Tests for the broker adapter layer: MockAdapter behavior + registry
factory selection. No real network calls are made anywhere in this file —
real adapters are only checked for correct construction/class identity."""
import pytest

from app.brokers.angelone import AngelOneAdapter
from app.brokers.base import BrokerAdapter
from app.brokers.dhan import DhanAdapter
from app.brokers.fyers import FyersAdapter
from app.brokers.mock import MockAdapter
from app.brokers.registry import get_adapter
from app.brokers.schemas import OrderRequest
from app.brokers.upstox import UpstoxAdapter
from app.models.broker_connection import BROKERS


# ── MockAdapter ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mock_adapter_get_holdings_shape():
    adapter = MockAdapter()
    holdings = await adapter.get_holdings()

    assert len(holdings) >= 4
    symbols = {h.symbol for h in holdings}
    assert {"RELIANCE", "TCS", "INFY", "HDFCBANK"}.issubset(symbols)
    for h in holdings:
        assert h.quantity > 0
        assert h.avg_price > 0
        assert h.current_price is not None and h.current_price > 0


@pytest.mark.asyncio
async def test_mock_adapter_get_quote_known_and_unknown_symbol():
    adapter = MockAdapter()

    quote = await adapter.get_quote("RELIANCE", "NSE")
    assert quote.symbol == "RELIANCE"
    assert quote.last_price > 0

    # Unknown symbols still get a deterministic, non-zero quote rather than
    # erroring — paper mode must always be able to fill an order.
    unknown_quote_1 = await adapter.get_quote("ZZZZ", "NSE")
    unknown_quote_2 = await adapter.get_quote("ZZZZ", "NSE")
    assert unknown_quote_1.last_price == unknown_quote_2.last_price
    assert unknown_quote_1.last_price > 0


@pytest.mark.asyncio
async def test_mock_adapter_place_order_is_paper_and_immediate_fill():
    adapter = MockAdapter()
    order = OrderRequest(symbol="TCS", exchange="NSE", side="buy", quantity=5, order_type="market")

    result = await adapter.place_order(order)

    assert result.is_paper is True
    assert result.status == "filled"
    assert result.symbol == "TCS"
    assert result.quantity == 5
    assert result.price is not None and result.price > 0
    assert result.broker_order_id.startswith("PAPER-")


@pytest.mark.asyncio
async def test_mock_adapter_place_order_never_reaches_a_real_broker(monkeypatch):
    """Sanity check for the hard safety rule: MockAdapter.place_order must
    not construct/use an httpx client at all."""
    import httpx

    def _forbidden(*args, **kwargs):
        raise AssertionError("MockAdapter.place_order must never make an HTTP call")

    monkeypatch.setattr(httpx.AsyncClient, "__init__", _forbidden)

    adapter = MockAdapter()
    order = OrderRequest(symbol="INFY", exchange="NSE", side="sell", quantity=1)
    result = await adapter.place_order(order)
    assert result.is_paper is True


@pytest.mark.asyncio
async def test_mock_adapter_get_order_status_and_cancel_roundtrip():
    adapter = MockAdapter()
    order = OrderRequest(symbol="HDFCBANK", exchange="NSE", side="buy", quantity=2)
    placed = await adapter.place_order(order)

    status = await adapter.get_order_status(placed.broker_order_id)
    assert status.broker_order_id == placed.broker_order_id
    assert status.status == "filled"

    cancelled = await adapter.cancel_order(placed.broker_order_id)
    # Already filled in paper mode -> cancel is a no-op that says so.
    assert "cannot cancel" in (cancelled.message or "").lower()


@pytest.mark.asyncio
async def test_mock_adapter_get_funds_and_authenticate():
    adapter = MockAdapter()
    funds = await adapter.get_funds()
    assert funds.available_cash > 0
    assert funds.total_balance >= funds.available_cash

    auth = await adapter.authenticate({})
    assert auth.success is True


# ── registry.get_adapter ─────────────────────────────────────────────────


@pytest.mark.parametrize("broker", BROKERS)
def test_registry_paper_mode_always_returns_mock_adapter(broker):
    adapter = get_adapter(broker, "paper", credentials={"anything": "ignored"})
    assert isinstance(adapter, MockAdapter)
    assert not isinstance(adapter, BrokerAdapter) or isinstance(adapter, MockAdapter)


@pytest.mark.parametrize(
    "broker,expected_cls",
    [
        ("dhan", DhanAdapter),
        ("angelone", AngelOneAdapter),
        ("upstox", UpstoxAdapter),
        ("fyers", FyersAdapter),
    ],
)
def test_registry_live_mode_returns_correct_real_adapter(broker, expected_cls):
    adapter = get_adapter(broker, "live", credentials={"dummy": "value"})
    assert isinstance(adapter, expected_cls)
    assert isinstance(adapter, BrokerAdapter)


def test_registry_unsupported_broker_in_live_mode_raises():
    from app.core.errors import AppError

    with pytest.raises(AppError):
        get_adapter("not_a_real_broker", "live", credentials={})


def test_registry_invalid_mode_raises():
    from app.core.errors import AppError

    with pytest.raises(AppError):
        get_adapter("dhan", "sandbox", credentials={})


def test_every_real_adapter_implements_the_full_broker_adapter_interface():
    for cls in (DhanAdapter, AngelOneAdapter, UpstoxAdapter, FyersAdapter):
        for method in (
            "authenticate",
            "get_holdings",
            "get_positions",
            "get_funds",
            "get_quote",
            "place_order",
            "get_order_status",
            "cancel_order",
        ):
            assert hasattr(cls, method)
        adapter = cls(credentials={})
        assert isinstance(adapter, BrokerAdapter)
