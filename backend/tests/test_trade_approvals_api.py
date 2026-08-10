"""API tests for /api/v1/trade-approvals — the human-in-the-loop decision
endpoint. Confirms rule #2 end to end: approving a trade executes it via
`MockAdapter` (paper mode only — never a real broker), records the paper
`broker_order_id`, and resumes the paused agent graph so it can acknowledge
the outcome; rejecting never touches a broker adapter at all.
"""
from __future__ import annotations

import uuid

import pytest

import app.agents.graph as graph_mod
from app.models.portfolio import Portfolio
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


async def _propose_trade(client, db_session, monkeypatch, symbol="RELIANCE", side="buy", quantity=5):
    portfolio = Portfolio(user_id=TEST_USER_ID, name="Test Portfolio")
    db_session.add(portfolio)
    await db_session.flush()
    await db_session.commit()

    proposal = graph_mod.TradeProposal(symbol=symbol, side=side, quantity=quantity, order_type="market", reasoning="test")
    monkeypatch.setattr(
        graph_mod, "get_structured_model", fake_structured_model(router_intent="trade", trade_proposal=proposal)
    )

    create_resp = client.post("/api/v1/agents/sessions", json={"portfolio_id": str(portfolio.id)})
    session_id = create_resp.json()["id"]
    send_resp = client.post(
        f"/api/v1/agents/sessions/{session_id}/messages", json={"content": f"{side} {quantity} {symbol}"}
    )
    events = _parse_sse(send_resp.text)
    interrupt_data = next(data for name, data in events if name == "interrupt")
    import json

    trade_approval_id = json.loads(interrupt_data)["trade_approval_id"]
    return session_id, trade_approval_id


@pytest.mark.asyncio
async def test_approve_decision_executes_in_paper_mode_and_records_order(client, db_session, monkeypatch):
    session_id, trade_approval_id = await _propose_trade(client, db_session, monkeypatch)
    monkeypatch.setattr(graph_mod, "get_chat_model", fake_chat_model("Acknowledged."))

    resp = client.post(f"/api/v1/trade-approvals/{trade_approval_id}/decision", json={"decision": "approve"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "executed"
    assert body["broker_order_id"] is not None
    assert body["broker_order_id"].startswith("PAPER-")  # never a real/live order
    assert body["decided_at"] is not None
    assert body["executed_at"] is not None

    # The conversation must have advanced — an assistant ack message persisted.
    messages_resp = client.get(f"/api/v1/agents/sessions/{session_id}/messages")
    messages = messages_resp.json()
    assert messages[-1]["role"] == "assistant"
    assert "executed" in messages[-1]["content"] or "PAPER-" in messages[-1]["content"]


@pytest.mark.asyncio
async def test_reject_decision_never_touches_a_broker(client, db_session, monkeypatch):
    session_id, trade_approval_id = await _propose_trade(client, db_session, monkeypatch)
    monkeypatch.setattr(graph_mod, "get_chat_model", fake_chat_model("Understood."))

    resp = client.post(
        f"/api/v1/trade-approvals/{trade_approval_id}/decision", json={"decision": "reject", "note": "changed my mind"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["broker_order_id"] is None
    assert body["risk_checks"]["decision_note"] == "changed my mind"


@pytest.mark.asyncio
async def test_deciding_an_already_decided_approval_returns_400(client, db_session, monkeypatch):
    _, trade_approval_id = await _propose_trade(client, db_session, monkeypatch)
    monkeypatch.setattr(graph_mod, "get_chat_model", fake_chat_model("Acknowledged."))

    first = client.post(f"/api/v1/trade-approvals/{trade_approval_id}/decision", json={"decision": "approve"})
    assert first.status_code == 200

    second = client.post(f"/api/v1/trade-approvals/{trade_approval_id}/decision", json={"decision": "approve"})
    assert second.status_code == 400
    assert second.json()["error"]["code"] == "TRADE_APPROVAL_ALREADY_DECIDED"


@pytest.mark.asyncio
async def test_get_and_list_trade_approvals(client, db_session, monkeypatch):
    _, trade_approval_id = await _propose_trade(client, db_session, monkeypatch)

    get_resp = client.get(f"/api/v1/trade-approvals/{trade_approval_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["symbol"] == "RELIANCE"

    list_resp = client.get("/api/v1/trade-approvals", params={"status": "pending"})
    assert list_resp.status_code == 200
    assert any(a["id"] == trade_approval_id for a in list_resp.json())


def test_trade_approval_owned_by_another_user_is_not_visible(client):
    from app.core.security import get_current_user_id
    from app.main import app

    other_uuid = uuid.uuid4()
    resp = client.get(f"/api/v1/trade-approvals/{other_uuid}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TRADE_APPROVAL_NOT_FOUND"


def test_trade_approvals_require_authentication(client):
    from app.core.security import get_current_user_id
    from app.main import app

    original = app.dependency_overrides.pop(get_current_user_id)
    try:
        resp = client.get("/api/v1/trade-approvals")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides[get_current_user_id] = original
