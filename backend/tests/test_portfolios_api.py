"""API tests for /api/v1/portfolios' holdings CRUD and /movers.

Uses the same sqlite dependency-override `client` fixture as other API tests
(see conftest.py) — no real Supabase Postgres connection.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.models.transaction import Transaction


def _create_portfolio(client) -> str:
    resp = client.post("/api/v1/portfolios", json={"name": "Test Portfolio", "base_currency": "INR"})
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_manual_holding_supports_commodity_asset_class(client):
    portfolio_id = _create_portfolio(client)
    resp = client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={
            "symbol": "gold",
            "exchange": "mcx",
            "quantity": 10,
            "avg_price": 6000,
            "current_price": 6500,
            "asset_class": "commodity",
            "sector": "precious_metals",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["symbol"] == "GOLD"
    assert body["exchange"] == "MCX"
    assert body["asset_class"] == "commodity"
    # market_value/unrealized_pnl are computed via app/financial/allocation.py,
    # never invented in the endpoint: 10 * 6500 = 65000, pnl = 10*(6500-6000) = 5000
    assert body["market_value"] == 65000
    assert body["unrealized_pnl"] == 5000
    assert body["unrealized_pnl_percent"] == pytest.approx(8.3333, rel=1e-3)


def test_create_holding_rejects_invalid_asset_class(client):
    portfolio_id = _create_portfolio(client)
    resp = client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": "XYZ", "quantity": 1, "avg_price": 100, "asset_class": "not_a_real_class"},
    )
    assert resp.status_code == 422


def test_create_holding_rejects_duplicate_symbol_exchange(client):
    portfolio_id = _create_portfolio(client)
    payload = {"symbol": "SILVER", "exchange": "MCX", "quantity": 5, "avg_price": 80, "asset_class": "commodity"}
    first = client.post(f"/api/v1/portfolios/{portfolio_id}/holdings", json=payload)
    assert first.status_code == 201
    second = client.post(f"/api/v1/portfolios/{portfolio_id}/holdings", json=payload)
    assert second.status_code == 409


def test_delete_holding_removes_it(client):
    portfolio_id = _create_portfolio(client)
    created = client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": "TCS", "quantity": 5, "avg_price": 1000, "asset_class": "equity"},
    )
    holding_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/portfolios/{portfolio_id}/holdings/{holding_id}")
    assert deleted.status_code == 204

    listed = client.get(f"/api/v1/portfolios/{portfolio_id}/holdings")
    assert listed.json() == []


def test_delete_holding_404s_for_holding_in_another_portfolio(client):
    portfolio_a = _create_portfolio(client)
    portfolio_b = _create_portfolio(client)
    created = client.post(
        f"/api/v1/portfolios/{portfolio_a}/holdings",
        json={"symbol": "TCS", "quantity": 5, "avg_price": 1000, "asset_class": "equity"},
    )
    holding_id = created.json()["id"]

    resp = client.delete(f"/api/v1/portfolios/{portfolio_b}/holdings/{holding_id}")
    assert resp.status_code == 404


def test_movers_endpoint_ranks_real_holdings(client):
    portfolio_id = _create_portfolio(client)
    client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": "GOLD", "quantity": 10, "avg_price": 100, "current_price": 150, "asset_class": "commodity"},
    )
    client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": "SILVER", "quantity": 10, "avg_price": 100, "current_price": 80, "asset_class": "commodity"},
    )

    resp = client.get(f"/api/v1/portfolios/{portfolio_id}/movers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["gainers"][0]["symbol"] == "GOLD"
    assert body["losers"][0]["symbol"] == "SILVER"


def test_movers_endpoint_empty_portfolio(client):
    portfolio_id = _create_portfolio(client)
    resp = client.get(f"/api/v1/portfolios/{portfolio_id}/movers")
    assert resp.status_code == 200
    assert resp.json()["gainers"] == []
    assert resp.json()["losers"] == []


@pytest.mark.asyncio
async def test_performance_with_one_transaction_does_not_500(client, db_session):
    """Regression test for two real bugs only reachable once a portfolio has
    at least one transaction (this suite's other tests never create one):
    (1) `cagr`'s exponentiation overflowing when `years` is tiny and the
    end/start ratio is large, and (2) the `range` query parameter shadowing
    the `range()` builtin inside `get_performance`. Both crashed the whole
    endpoint with a 500 in the real running app before being fixed."""
    portfolio_id = _create_portfolio(client)
    client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"symbol": "TCS", "quantity": 100, "avg_price": 1000, "current_price": 4000, "asset_class": "equity"},
    )
    db_session.add(
        Transaction(
            portfolio_id=UUID(portfolio_id),
            symbol="TCS",
            side="buy",
            quantity=10,
            price=1000,
            executed_at=datetime.now(timezone.utc),
            source="manual",
        )
    )
    await db_session.commit()

    resp = client.get(f"/api/v1/portfolios/{portfolio_id}/performance?range=1M")
    assert resp.status_code == 200
    body = resp.json()
    # The metric that overflows should degrade to null, not 500 the request.
    assert body["cagr"] is None
