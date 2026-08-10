"""API tests for /api/v1/agents — sessions, message history, and the SSE
streaming chat endpoint. Uses the `client` fixture from conftest.py (in-memory
SQLite, fixed test user, MemorySaver checkpointer — see conftest.py) plus
`db_session` (same underlying SQLite database) to seed portfolio data.

All LLM calls are mocked via `tests/_agent_test_helpers.py`, monkeypatching
`app.agents.graph.get_chat_model`/`get_structured_model` — no real provider
call, no API credits spent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app.agents.graph as graph_mod
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.transaction import Transaction
from app.models.trade_approval import TradeApproval
from tests._agent_test_helpers import fake_chat_model, fake_structured_model
from tests.conftest import TEST_USER_ID


def _parse_sse(text: str) -> list[tuple[str, str]]:
    events = []
    for block in text.strip("\n").split("\n\n"):
        if not block.strip():
            continue
        event_name, data_line = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_line = line[len("data:") :].strip()
        if event_name is not None:
            events.append((event_name, data_line))
    return events


async def _seed_portfolio_with_holdings(db_session) -> Portfolio:
    portfolio = Portfolio(user_id=TEST_USER_ID, name="Test Portfolio")
    db_session.add(portfolio)
    await db_session.flush()
    db_session.add(Holding(portfolio_id=portfolio.id, symbol="TCS", quantity=10, avg_price=100, current_price=150))
    now = datetime.now(timezone.utc)
    db_session.add(Transaction(portfolio_id=portfolio.id, symbol="TCS", side="buy", quantity=5, price=100, executed_at=now - timedelta(days=100)))
    db_session.add(Transaction(portfolio_id=portfolio.id, symbol="TCS", side="buy", quantity=5, price=100, executed_at=now))
    await db_session.commit()
    return portfolio


def test_create_and_list_sessions(client):
    resp = client.post("/api/v1/agents/sessions", json={"title": "My session"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "My session"
    assert body["portfolio_id"] is None

    list_resp = client.get("/api/v1/agents/sessions")
    assert list_resp.status_code == 200
    assert any(s["id"] == body["id"] for s in list_resp.json())


def test_get_messages_for_nonexistent_session_returns_404(client):
    resp = client.get(f"/api/v1/agents/sessions/{uuid.uuid4()}/messages")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "AGENT_SESSION_NOT_FOUND"


def test_session_owned_by_another_user_is_not_visible(client):
    from app.core.security import get_current_user_id
    from app.main import app

    create_resp = client.post("/api/v1/agents/sessions", json={"title": "Mine"})
    session_id = create_resp.json()["id"]

    async def _as_other_user() -> str:
        return str(uuid.uuid4())

    original = app.dependency_overrides[get_current_user_id]
    app.dependency_overrides[get_current_user_id] = _as_other_user
    try:
        resp = client.get(f"/api/v1/agents/sessions/{session_id}/messages")
        assert resp.status_code == 404
    finally:
        app.dependency_overrides[get_current_user_id] = original


def test_agents_require_authentication(client):
    from app.core.security import get_current_user_id
    from app.main import app

    original = app.dependency_overrides.pop(get_current_user_id)
    try:
        resp = client.get("/api/v1/agents/sessions")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides[get_current_user_id] = original


@pytest.mark.asyncio
async def test_send_message_streams_tool_call_and_done_for_portfolio_intent(client, db_session, monkeypatch):
    portfolio = await _seed_portfolio_with_holdings(db_session)
    monkeypatch.setattr(graph_mod, "get_structured_model", fake_structured_model(router_intent="portfolio"))
    monkeypatch.setattr(graph_mod, "get_chat_model", fake_chat_model("Your portfolio grew from 500.0 to 1500.0."))

    create_resp = client.post("/api/v1/agents/sessions", json={"portfolio_id": str(portfolio.id)})
    session_id = create_resp.json()["id"]

    resp = client.post(f"/api/v1/agents/sessions/{session_id}/messages", json={"content": "How is my portfolio doing?"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse(resp.text)
    event_names = [name for name, _ in events]
    assert "tool_call" in event_names
    assert "token" in event_names
    assert event_names[-1] == "done"

    tool_call_payloads = [data for name, data in events if name == "tool_call"]
    assert any("compute_performance" in p for p in tool_call_payloads)

    # The final assistant message must be persisted.
    messages_resp = client.get(f"/api/v1/agents/sessions/{session_id}/messages")
    roles = [m["role"] for m in messages_resp.json()]
    assert roles == ["user", "assistant"]
    assert messages_resp.json()[-1]["content"] == "Your portfolio grew from 500.0 to 1500.0."


@pytest.mark.asyncio
async def test_send_message_trade_intent_returns_interrupt_event_and_creates_pending_approval(client, db_session, monkeypatch):
    portfolio = await _seed_portfolio_with_holdings(db_session)
    proposal = graph_mod.TradeProposal(symbol="reliance", side="buy", quantity=5, order_type="market", reasoning="User asked directly.")
    monkeypatch.setattr(
        graph_mod, "get_structured_model", fake_structured_model(router_intent="trade", trade_proposal=proposal)
    )

    create_resp = client.post("/api/v1/agents/sessions", json={"portfolio_id": str(portfolio.id)})
    session_id = create_resp.json()["id"]

    resp = client.post(f"/api/v1/agents/sessions/{session_id}/messages", json={"content": "Buy 5 shares of RELIANCE"})
    assert resp.status_code == 200
    events = _parse_sse(resp.text)
    event_names = [name for name, _ in events]
    assert "interrupt" in event_names
    assert event_names[-1] == "done"

    interrupt_data = next(data for name, data in events if name == "interrupt")
    assert "RELIANCE" in interrupt_data
    assert "trade_approval_id" in interrupt_data

    from sqlalchemy import select

    result = await db_session.execute(select(TradeApproval).where(TradeApproval.symbol == "RELIANCE"))
    approval = result.scalar_one()
    assert approval.status == "pending"
    assert approval.broker_order_id is None  # never executed by the graph itself
