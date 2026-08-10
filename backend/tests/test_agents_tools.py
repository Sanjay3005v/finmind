"""Tests for app/agents/tools.py — the per-request tool factory.

Uses `db_session`/`db_engine` (in-memory SQLite, from conftest.py) directly
rather than the `client` fixture, since these are plain async functions, not
HTTP endpoints. `research_lookup` monkeypatches `hybrid_search`/`rerank` at
the module level (same pattern as tests/test_research_api.py) — no real
pgvector/OpenAI call.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

import app.agents.tools as tools_module
from app.agents.tools import AgentToolError, build_tools
from app.models._supabase_auth_stub import auth_users
from app.models.holding import Holding
from app.models.portfolio import Portfolio
from app.models.transaction import Transaction
from app.rag.retrieval import RetrievedChunk


async def _make_user_and_portfolio(db_session):
    user_id = uuid.uuid4()
    await db_session.execute(auth_users.insert().values(id=user_id))
    portfolio = Portfolio(user_id=user_id, name="Test Portfolio")
    db_session.add(portfolio)
    await db_session.flush()
    return user_id, portfolio


@pytest.mark.asyncio
async def test_get_holdings_summary_returns_raw_holdings_no_computed_stats(db_session):
    user_id, portfolio = await _make_user_and_portfolio(db_session)
    db_session.add(Holding(portfolio_id=portfolio.id, symbol="TCS", quantity=10, avg_price=100, current_price=150))
    await db_session.flush()

    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    result = await tools["get_holdings_summary"].ainvoke({})

    assert result["count"] == 1
    assert result["holdings"][0]["symbol"] == "TCS"
    assert result["holdings"][0]["quantity"] == 10.0
    assert "sharpe_ratio" not in result and "cagr" not in result  # no computed stats


@pytest.mark.asyncio
async def test_get_holdings_summary_empty_portfolio_returns_explicit_empty_list_not_error(db_session):
    user_id, portfolio = await _make_user_and_portfolio(db_session)
    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    result = await tools["get_holdings_summary"].ainvoke({})
    assert result["count"] == 0
    assert result["holdings"] == []


@pytest.mark.asyncio
async def test_tools_raise_agent_tool_error_when_no_portfolio_bound(db_session):
    user_id = uuid.uuid4()
    await db_session.execute(auth_users.insert().values(id=user_id))
    tools = {t.name: t for t in build_tools(db_session, str(user_id), None)}

    with pytest.raises(AgentToolError):
        await tools["get_holdings_summary"].ainvoke({})
    with pytest.raises(AgentToolError):
        await tools["compute_risk_metrics"].ainvoke({})


@pytest.mark.asyncio
async def test_compute_performance_uses_real_financial_functions(db_session):
    user_id, portfolio = await _make_user_and_portfolio(db_session)
    db_session.add(Holding(portfolio_id=portfolio.id, symbol="TCS", quantity=10, avg_price=100, current_price=150))
    now = datetime.now(timezone.utc)
    # Two transactions 100 days apart so the equity curve has a real span
    # (a single transaction would make first_ts == last_ts, degenerating
    # the CAGR time base to ~0 years — see app/api/v1/portfolios.py's
    # `_build_equity_curve` docstring for why this schema's equity curve is
    # book-value-based, not a true daily price series).
    db_session.add(
        Transaction(portfolio_id=portfolio.id, symbol="TCS", side="buy", quantity=5, price=100, executed_at=now - timedelta(days=100))
    )
    db_session.add(
        Transaction(portfolio_id=portfolio.id, symbol="TCS", side="buy", quantity=5, price=100, executed_at=now)
    )
    await db_session.flush()

    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    result = await tools["compute_performance"].ainvoke({"range": "ALL"})

    assert result["start_value"] == 500.0
    assert result["end_value"] == 1500.0
    assert result["simple_return"] == pytest.approx(2.0)
    # cagr computed via app.financial.returns.cagr — must be a real number, not fabricated.
    from app.financial import cagr as real_cagr

    years = max(100 / 365.25, 1 / 365.25)
    assert result["cagr"] == pytest.approx(real_cagr(500.0, 1500.0, years))


@pytest.mark.asyncio
async def test_compute_performance_rejects_invalid_range(db_session):
    user_id, portfolio = await _make_user_and_portfolio(db_session)
    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    with pytest.raises(AgentToolError):
        await tools["compute_performance"].ainvoke({"range": "5Y"})


@pytest.mark.asyncio
async def test_compute_risk_metrics_includes_concentration_score_and_no_fabricated_beta(db_session):
    user_id, portfolio = await _make_user_and_portfolio(db_session)
    db_session.add(Holding(portfolio_id=portfolio.id, symbol="TCS", quantity=10, avg_price=100, current_price=100))
    await db_session.flush()

    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    result = await tools["compute_risk_metrics"].ainvoke({})

    assert result["concentration_score"] == 1.0  # single holding -> fully concentrated
    assert result["beta"] is None
    assert "beta_note" in result


@pytest.mark.asyncio
async def test_compute_allocation_breakdown_matches_real_allocation_function(db_session):
    user_id, portfolio = await _make_user_and_portfolio(db_session)
    db_session.add(
        Holding(portfolio_id=portfolio.id, symbol="TCS", quantity=10, avg_price=100, current_price=100, asset_class="equity", sector="IT")
    )
    db_session.add(
        Holding(portfolio_id=portfolio.id, symbol="CASH", quantity=1, avg_price=1000, current_price=1000, asset_class="cash", sector=None)
    )
    await db_session.flush()

    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    result = await tools["compute_allocation_breakdown"].ainvoke({})

    assert result["total_market_value"] == 2000.0
    assert result["by_asset_class"]["percentage"]["equity"] == pytest.approx(50.0)
    assert result["by_asset_class"]["percentage"]["cash"] == pytest.approx(50.0)


@pytest.mark.asyncio
async def test_research_lookup_returns_retrieved_chunks_not_a_synthesized_answer(db_session, monkeypatch):
    user_id, portfolio = await _make_user_and_portfolio(db_session)
    fake_chunk = RetrievedChunk(
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        document_title="Q3 Earnings",
        chunk_index=0,
        content="Revenue grew 12% year over year.",
        score=0.9,
    )

    async def _fake_hybrid_search(query, db, uid, top_k=10):
        return [fake_chunk]

    async def _fake_rerank(query, candidates, top_n=5):
        return candidates

    monkeypatch.setattr(tools_module, "hybrid_search", _fake_hybrid_search)
    monkeypatch.setattr(tools_module, "rerank", _fake_rerank)

    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    result = await tools["research_lookup"].ainvoke({"query": "How did revenue perform?"})

    assert result["count"] == 1
    assert result["chunks"][0]["document_title"] == "Q3 Earnings"
    assert result["chunks"][0]["content"] == "Revenue grew 12% year over year."
    assert "answer" not in result  # must not synthesize — only raw evidence


@pytest.mark.asyncio
async def test_research_lookup_rejects_empty_query(db_session):
    user_id, portfolio = await _make_user_and_portfolio(db_session)
    tools = {t.name: t for t in build_tools(db_session, str(user_id), str(portfolio.id))}
    with pytest.raises(AgentToolError):
        await tools["research_lookup"].ainvoke({"query": "   "})
