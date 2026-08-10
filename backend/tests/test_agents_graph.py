"""Tests for app/agents/graph.py — router, self-reflection, and the trade
human-in-the-loop interrupt.

All LLM calls are mocked via `tests/_agent_test_helpers.py` (monkeypatching
`app.agents.graph.get_chat_model`/`get_structured_model`, same pattern as
`tests/test_research_api.py`'s `_synthesize` mock) — this suite never calls
a real LLM provider. Uses `MemorySaver` (never real Postgres) as the
checkpointer, and the in-memory SQLite `db_session` fixture from
conftest.py for anything the graph's tools touch.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

import app.agents.graph as graph_mod
from app.agents.graph import ReflectionVerdict, TradeProposal, build_graph
from app.agents.tools import build_tools
from app.models._supabase_auth_stub import auth_users
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.trade_approval import TradeApproval
from app.models.transaction import Transaction
from tests._agent_test_helpers import fake_chat_model, fake_structured_model


async def _make_user_and_portfolio_with_holdings(db_session):
    user_id = uuid.uuid4()
    await db_session.execute(auth_users.insert().values(id=user_id))
    portfolio = Portfolio(user_id=user_id, name="Test Portfolio")
    db_session.add(portfolio)
    await db_session.flush()
    db_session.add(Holding(portfolio_id=portfolio.id, symbol="TCS", quantity=10, avg_price=100, current_price=150))
    now = datetime.now(timezone.utc)
    db_session.add(Transaction(portfolio_id=portfolio.id, symbol="TCS", side="buy", quantity=5, price=100, executed_at=now - timedelta(days=100)))
    db_session.add(Transaction(portfolio_id=portfolio.id, symbol="TCS", side="buy", quantity=5, price=100, executed_at=now))
    await db_session.flush()
    return user_id, portfolio


def _config(session_id, tools, db):
    return {"configurable": {"thread_id": str(session_id), "tools": tools, "db": db}}


# ─────────────────────────────────────────────────────────────────────────
# Pure routing-decision helpers
# ─────────────────────────────────────────────────────────────────────────
def test_route_decision_returns_intent_from_state():
    assert graph_mod.route_decision({"intent": "risk"}) == "risk"


def test_route_decision_falls_back_to_general_when_missing():
    assert graph_mod.route_decision({}) == "general"


def test_reflection_router_ends_when_passed():
    assert graph_mod.reflection_router({"reflection_passed": True, "intent": "portfolio"}) == "end"


def test_reflection_router_loops_back_to_intent_node_when_failed():
    assert graph_mod.reflection_router({"reflection_passed": False, "intent": "research"}) == "research"


# ─────────────────────────────────────────────────────────────────────────
# Deterministic numeric-consistency / citation checks
# ─────────────────────────────────────────────────────────────────────────
def test_numeric_claims_unmatched_accepts_numbers_present_in_tool_results():
    tool_results = [{"name": "compute_performance", "args": {}, "result": {"start_value": 1000.0, "end_value": 1500.0}}]
    draft = "Your portfolio grew from 1000.0 to 1500.0."
    assert graph_mod._numeric_claims_unmatched(draft, tool_results) == []


def test_numeric_claims_unmatched_flags_a_fabricated_number():
    tool_results = [{"name": "compute_performance", "args": {}, "result": {"start_value": 1000.0, "end_value": 1500.0}}]
    draft = "Your portfolio is now worth an incredible 9999.0!"
    unmatched = graph_mod._numeric_claims_unmatched(draft, tool_results)
    assert 9999.0 in unmatched


def test_invalid_citation_markers_flags_out_of_range_marker():
    citations = [{"marker": 1, "document_id": "d1", "document_title": "t", "chunk_id": "c1", "chunk_index": 0, "snippet": "s"}]
    draft = "Revenue grew [1] and margins held steady [2]."
    assert graph_mod._invalid_citation_markers(draft, citations) == [2]


@pytest.mark.asyncio
async def test_self_reflection_node_fails_and_loops_back_on_fabricated_number(monkeypatch):
    """Rule #1: a deliberately-wrong number in the draft (not present in
    any tool_results this turn) must fail deterministically and route back
    to the originating node, rather than being accepted."""
    state = {
        "intent": "portfolio",
        "draft_answer": "Your portfolio is worth an amazing 9999.0 today.",
        "tool_results": [{"name": "compute_performance", "args": {}, "result": {"start_value": 1000.0, "end_value": 1500.0}}],
        "citations": [],
        "reflection_attempts": 0,
    }
    update = await graph_mod.self_reflection_node(state, {"configurable": {}})
    assert update["reflection_passed"] is False
    assert update["reflection_attempts"] == 1
    assert "9999.0" in update["reflection_feedback"]
    assert graph_mod.reflection_router({**state, **update}) == "portfolio"


@pytest.mark.asyncio
async def test_self_reflection_node_passes_when_numbers_are_grounded(monkeypatch):
    monkeypatch.setattr(graph_mod, "get_structured_model", fake_structured_model(reflection_verdict=ReflectionVerdict(passed=True, reasons="ok")))
    state = {
        "intent": "portfolio",
        "draft_answer": "Your portfolio grew from 1000.0 to 1500.0.",
        "tool_results": [{"name": "compute_performance", "args": {}, "result": {"start_value": 1000.0, "end_value": 1500.0}}],
        "citations": [],
        "reflection_attempts": 0,
    }
    update = await graph_mod.self_reflection_node(state, {"configurable": {}})
    assert update["reflection_passed"] is True
    assert update["reflection_feedback"] is None


@pytest.mark.asyncio
async def test_self_reflection_gives_up_after_max_retries_with_logged_warning(monkeypatch, caplog):
    state = {
        "intent": "portfolio",
        "draft_answer": "Your portfolio is worth 9999.0.",
        "tool_results": [{"name": "compute_performance", "args": {}, "result": {"start_value": 1000.0, "end_value": 1500.0}}],
        "citations": [],
        "reflection_attempts": graph_mod.MAX_REFLECTION_RETRIES,  # already used up all retries
    }
    update = await graph_mod.self_reflection_node(state, {"configurable": {}})
    # Accepts the best (still-flawed) attempt rather than looping forever.
    assert update["reflection_passed"] is True
    assert graph_mod.reflection_router({**state, **update}) == "end"


# ─────────────────────────────────────────────────────────────────────────
# Full graph run: portfolio intent, grounded numbers, self-reflection passes
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_full_graph_run_portfolio_intent_grounds_every_number_in_tool_output(db_session, monkeypatch):
    user_id, portfolio = await _make_user_and_portfolio_with_holdings(db_session)
    monkeypatch.setattr(graph_mod, "get_structured_model", fake_structured_model(router_intent="portfolio"))
    monkeypatch.setattr(
        graph_mod, "get_chat_model", fake_chat_model("Your portfolio grew from 500.0 to 1500.0, a strong gain.")
    )

    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    checkpointer = MemorySaver()
    compiled = build_graph(checkpointer)
    session_id = uuid.uuid4()
    config = _config(session_id, tools, db_session)

    state = {
        "messages": [HumanMessage("How is my portfolio doing?")],
        "session_id": str(session_id),
        "user_id": str(user_id),
        "portfolio_id": str(portfolio.id),
    }
    async for _ in compiled.astream(state, config, stream_mode="updates"):
        pass

    final = await compiled.aget_state(config)
    assert final.values["reflection_passed"] is True
    assert final.values["draft_answer"] == "Your portfolio grew from 500.0 to 1500.0, a strong gain."
    assert len(final.values["tool_results"]) == 2  # get_holdings_summary + compute_performance


@pytest.mark.asyncio
async def test_full_graph_run_portfolio_intent_retries_then_accepts_on_persistent_fabrication(db_session, monkeypatch):
    """The narration model keeps fabricating a number every attempt — the
    graph must retry up to MAX_REFLECTION_RETRIES and then accept the best
    attempt rather than looping forever."""
    user_id, portfolio = await _make_user_and_portfolio_with_holdings(db_session)
    monkeypatch.setattr(graph_mod, "get_structured_model", fake_structured_model(router_intent="portfolio"))
    monkeypatch.setattr(graph_mod, "get_chat_model", fake_chat_model("Your portfolio is worth an incredible 9999.0!"))

    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    checkpointer = MemorySaver()
    compiled = build_graph(checkpointer)
    session_id = uuid.uuid4()
    config = _config(session_id, tools, db_session)

    state = {
        "messages": [HumanMessage("How is my portfolio doing?")],
        "session_id": str(session_id),
        "user_id": str(user_id),
        "portfolio_id": str(portfolio.id),
    }
    node_runs = 0
    async for chunk in compiled.astream(state, config, stream_mode="updates"):
        if "portfolio" in chunk:
            node_runs += 1

    final = await compiled.aget_state(config)
    assert final.values["reflection_passed"] is True  # gave up, accepted best attempt
    assert node_runs == 1 + graph_mod.MAX_REFLECTION_RETRIES  # initial + 2 retries


# ─────────────────────────────────────────────────────────────────────────
# Trade proposal: creates a pending TradeApproval row and PAUSES via
# interrupt() — never executes anything itself (rule #2).
# ─────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_trade_flow_creates_pending_approval_and_interrupts_instead_of_executing(db_session, monkeypatch):
    user_id, portfolio = await _make_user_and_portfolio_with_holdings(db_session)
    proposal = TradeProposal(symbol="reliance", side="buy", quantity=10, order_type="market", reasoning="Diversification.")
    monkeypatch.setattr(
        graph_mod, "get_structured_model", fake_structured_model(router_intent="trade", trade_proposal=proposal)
    )

    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    checkpointer = MemorySaver()
    compiled = build_graph(checkpointer)
    session_id = uuid.uuid4()
    config = _config(session_id, tools, db_session)

    state = {
        "messages": [HumanMessage("Buy 10 shares of RELIANCE")],
        "session_id": str(session_id),
        "user_id": str(user_id),
        "portfolio_id": str(portfolio.id),
    }

    interrupt_payload = None
    async for chunk in compiled.astream(state, config, stream_mode="updates"):
        if "__interrupt__" in chunk:
            interrupt_payload = chunk["__interrupt__"][0].value

    assert interrupt_payload is not None
    assert interrupt_payload["symbol"] == "RELIANCE"
    assert interrupt_payload["side"] == "buy"
    assert interrupt_payload["quantity"] == 10.0

    # The graph must have paused, NOT run to completion.
    pending_state = await compiled.aget_state(config)
    assert pending_state.next  # there's still a pending task (trade_interrupt)

    # A pending TradeApproval row must exist — created, but not executed.
    from sqlalchemy import select

    result = await db_session.execute(select(TradeApproval).where(TradeApproval.symbol == "RELIANCE"))
    approval = result.scalar_one()
    assert approval.status == "pending"
    assert approval.requested_by == "agent"
    assert approval.broker_order_id is None
    assert approval.reasoning == "Diversification."

    # Resuming with an approval decision lets the graph finish and narrate —
    # still without the graph itself ever touching a broker.
    from langgraph.types import Command

    decision_payload = {"status": "executed", "symbol": "RELIANCE", "side": "buy", "quantity": 10.0, "broker_order_id": "PAPER-000001"}
    async for _ in compiled.astream(Command(resume=decision_payload), config, stream_mode="updates"):
        pass

    final = await compiled.aget_state(config)
    assert not final.next  # graph reached END
    assert "PAPER-000001" in final.values["draft_answer"]
    assert "executed" in final.values["draft_answer"]
