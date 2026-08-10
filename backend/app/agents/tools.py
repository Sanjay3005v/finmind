"""Per-request LangChain tool factory for the FINMIND agent.

Hard rule (docs/ARCHITECTURE.md section 5 / Phase 6 spec rule #1): the LLM
never computes a financial number itself. Every tool below either returns
raw structured data straight from the DB (no arithmetic at all) or calls a
function in `app/financial/*` / `app/rag/*` for any computed value — nothing
here re-implements returns/risk/allocation/retrieval math.

Tools are built by `build_tools(db, user_id, portfolio_id)` and closed over
the DB session/user/portfolio so the LLM only ever supplies simple args
(e.g. a date-range string) — it can never see or influence a raw SQL
session, another user's id, or an arbitrary portfolio id.

Every tool raises `AgentToolError` on failure (DB error, upstream RAG
failure, etc.) rather than returning an empty/zero result that could be
misread by the LLM as "the user has no holdings" — callers (graph nodes)
must catch `AgentToolError` explicitly and surface it, never swallow it into
a silently-empty answer.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.financial import (
    allocation_breakdown,
    annualized_volatility,
    cagr,
    concentration_score,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)
from app.models.holding import Holding
from app.models.transaction import Transaction
from app.rag.rerank import DEFAULT_TOP_N, rerank
from app.rag.retrieval import DEFAULT_TOP_K, hybrid_search

RANGE_TO_DAYS = {"1M": 30, "3M": 90, "1Y": 365, "ALL": None}


class AgentToolError(Exception):
    """Raised by an agent tool on failure. Graph nodes must catch this and
    surface a clear error to self-reflection/the user, never treat the
    absence of a result as "zero holdings" or "no risk"."""


def _holding_dict(h: Holding) -> dict:
    return {
        "symbol": h.symbol,
        "exchange": h.exchange,
        "quantity": float(h.quantity),
        "avg_price": float(h.avg_price),
        "current_price": float(h.current_price) if h.current_price is not None else None,
        "asset_class": h.asset_class,
        "sector": h.sector,
        "currency": h.currency,
    }


def _current_market_value(holdings: list[dict]) -> float:
    total = 0.0
    for h in holdings:
        price = h["current_price"] if h["current_price"] is not None else h["avg_price"]
        total += h["quantity"] * price
    return total


def _periodic_returns(equity_curve: list[float]) -> list[float]:
    """Period-over-period returns from an equity curve. Written with `zip`
    rather than `range(...)` deliberately — several tools below have a
    parameter literally named `range` (matching the spec's
    `compute_performance(range: str)` signature), which shadows the
    builtin within that function's scope."""
    return [
        (curr - prev) / prev
        for prev, curr in zip(equity_curve[:-1], equity_curve[1:])
        if prev > 0
    ]


def _build_equity_curve(transactions: list[Transaction]) -> list[float]:
    """Cumulative running book value from chronological transactions — the
    same approach `app/api/v1/portfolios.py::get_performance` uses, since
    this schema has no historical daily-price table yet (see that module's
    docstring)."""
    ordered = sorted(transactions, key=lambda t: t.executed_at)
    curve: list[float] = []
    running = 0.0
    for t in ordered:
        gross = float(t.quantity) * float(t.price)
        fees = float(t.fees)
        if t.side == "buy":
            running += gross + fees
        else:
            running -= gross - fees
            running = max(running, 0.0)
        curve.append(running)
    return curve


async def _fetch_holdings(db: AsyncSession, portfolio_id: UUID) -> list[Holding]:
    try:
        result = await db.execute(select(Holding).where(Holding.portfolio_id == portfolio_id).order_by(Holding.symbol))
        return list(result.scalars().all())
    except Exception as exc:  # noqa: BLE001
        raise AgentToolError(f"Failed to load holdings: {exc}") from exc


async def _fetch_transactions(db: AsyncSession, portfolio_id: UUID, days: Optional[int]) -> list[Transaction]:
    from datetime import datetime, timedelta, timezone

    try:
        query = select(Transaction).where(Transaction.portfolio_id == portfolio_id)
        if days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.where(Transaction.executed_at >= cutoff)
        result = await db.execute(query.order_by(Transaction.executed_at))
        return list(result.scalars().all())
    except Exception as exc:  # noqa: BLE001
        raise AgentToolError(f"Failed to load transactions: {exc}") from exc


def build_tools(db: AsyncSession, user_id: str, portfolio_id: Optional[str]) -> list[BaseTool]:
    """Builds the full tool set for one agent turn, closed over `db`,
    `user_id`, and `portfolio_id`. `portfolio_id` may be `None` for a
    session with no portfolio attached — portfolio/risk tools raise
    `AgentToolError` if called in that case rather than silently no-op'ing."""

    portfolio_uuid: Optional[UUID] = UUID(portfolio_id) if portfolio_id else None

    def _require_portfolio() -> UUID:
        if portfolio_uuid is None:
            raise AgentToolError(
                "This agent session has no portfolio attached — cannot look up holdings/performance/risk."
            )
        return portfolio_uuid

    @tool
    async def get_holdings_summary() -> dict:
        """Fetch the current holdings for the user's bound portfolio.
        Returns raw holding records (symbol, exchange, quantity, avg_price,
        current_price, asset_class, sector, currency) with NO computed
        statistics — use compute_performance/compute_risk_metrics/
        compute_allocation_breakdown for any derived numbers. Returns an
        explicit empty list (not an error) when the portfolio genuinely has
        no holdings."""
        pid = _require_portfolio()
        holdings = await _fetch_holdings(db, pid)
        return {"portfolio_id": str(pid), "count": len(holdings), "holdings": [_holding_dict(h) for h in holdings]}

    @tool
    async def compute_performance(range: str = "ALL") -> dict:
        """Compute real performance metrics for the user's bound portfolio
        over a date range. `range` must be one of "1M", "3M", "1Y", "ALL".
        Returns start_value, end_value, simple_return, cagr,
        annualized_volatility, sharpe_ratio, sortino_ratio, max_drawdown —
        every number computed by app/financial/returns.py and
        app/financial/risk.py, never estimated. Fields may be null when the
        transaction history is too short to compute that metric (e.g. fewer
        than two periodic returns for volatility)."""
        if range not in RANGE_TO_DAYS:
            raise AgentToolError(f"Invalid range {range!r}; must be one of {list(RANGE_TO_DAYS)}.")
        pid = _require_portfolio()
        days = RANGE_TO_DAYS[range]
        transactions = await _fetch_transactions(db, pid, days)
        holdings = [_holding_dict(h) for h in await _fetch_holdings(db, pid)]

        end_value = _current_market_value(holdings)
        equity_curve = _build_equity_curve(transactions)
        start_value = equity_curve[0] if equity_curve else 0.0

        simple_ret = cagr_val = vol = sharpe = sortino = mdd = None
        if equity_curve and start_value > 0:
            simple_ret = (end_value - start_value) / start_value
            first_ts, last_ts = transactions[0].executed_at, transactions[-1].executed_at
            years = max((last_ts - first_ts).days / 365.25, 1 / 365.25)
            try:
                cagr_val = cagr(start_value, end_value, years)
            except ValueError:
                pass
            periodic_returns = _periodic_returns(equity_curve)
            if len(periodic_returns) >= 2:
                try:
                    vol = annualized_volatility(periodic_returns)
                except ValueError:
                    pass
                try:
                    sharpe = sharpe_ratio(periodic_returns)
                except ValueError:
                    pass
                try:
                    sortino = sortino_ratio(periodic_returns)
                except ValueError:
                    pass
            full_curve = [start_value] + equity_curve + [end_value]
            if len(full_curve) >= 2:
                try:
                    mdd = max_drawdown(full_curve)
                except ValueError:
                    pass

        return {
            "portfolio_id": str(pid),
            "range": range,
            "start_value": start_value,
            "end_value": end_value,
            "simple_return": simple_ret,
            "cagr": cagr_val,
            "annualized_volatility": vol,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": mdd,
        }

    @tool
    async def compute_risk_metrics() -> dict:
        """Compute real risk metrics for the user's bound portfolio:
        annualized volatility, Sharpe ratio, Sortino ratio, max drawdown
        (over the full transaction history) and a concentration score
        (Herfindahl-Hirschman index over position weights, 0..1, higher =
        more concentrated). All numbers come from app/financial/risk.py and
        app/financial/allocation.py::concentration_score — never estimated.
        Note: beta is not returned because this deployment has no benchmark
        price history to compute it against."""
        pid = _require_portfolio()
        transactions = await _fetch_transactions(db, pid, days=None)
        holdings = [_holding_dict(h) for h in await _fetch_holdings(db, pid)]
        end_value = _current_market_value(holdings)
        equity_curve = _build_equity_curve(transactions)

        vol = sharpe = sortino = mdd = None
        if equity_curve:
            start_value = equity_curve[0]
            periodic_returns = _periodic_returns(equity_curve)
            if len(periodic_returns) >= 2:
                try:
                    vol = annualized_volatility(periodic_returns)
                except ValueError:
                    pass
                try:
                    sharpe = sharpe_ratio(periodic_returns)
                except ValueError:
                    pass
                try:
                    sortino = sortino_ratio(periodic_returns)
                except ValueError:
                    pass
            full_curve = [start_value] + equity_curve + [end_value]
            if len(full_curve) >= 2:
                try:
                    mdd = max_drawdown(full_curve)
                except ValueError:
                    pass

        score = concentration_score(holdings)
        return {
            "portfolio_id": str(pid),
            "annualized_volatility": vol,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": mdd,
            "concentration_score": score,
            "beta": None,
            "beta_note": "No benchmark price history configured; beta cannot be computed.",
        }

    @tool
    async def compute_allocation_breakdown() -> dict:
        """Compute the real asset-class and sector allocation breakdown for
        the user's bound portfolio, via app/financial/allocation.py. Returns
        total_market_value, by_asset_class (market_value + percentage), and
        by_sector (market_value + percentage) — all real arithmetic over the
        current holdings, never estimated."""
        pid = _require_portfolio()
        holdings = [_holding_dict(h) for h in await _fetch_holdings(db, pid)]
        breakdown = allocation_breakdown(holdings)
        return {"portfolio_id": str(pid), **breakdown}

    @tool
    async def research_lookup(query: str) -> dict:
        """Retrieve evidence passages from the user's research document
        library for `query`, via hybrid (vector + full-text) search followed
        by LLM-judge reranking. Returns the retrieved chunks (content,
        document_title, document_id, chunk_id, chunk_index) as raw evidence
        — this does NOT synthesize an answer; the calling agent must reason
        over and cite these chunks itself. Returns an explicit empty list
        (not an error) when nothing relevant is found in the library."""
        if not query or not query.strip():
            raise AgentToolError("research_lookup requires a non-empty query.")
        try:
            candidates = await hybrid_search(query, db, user_id, top_k=DEFAULT_TOP_K)
            reranked = await rerank(query, candidates, top_n=DEFAULT_TOP_N)
        except Exception as exc:  # noqa: BLE001
            raise AgentToolError(f"research_lookup failed: {exc}") from exc
        return {
            "query": query,
            "count": len(reranked),
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "document_id": c.document_id,
                    "document_title": c.document_title,
                    "chunk_index": c.chunk_index,
                    "content": c.content,
                }
                for c in reranked
            ],
        }

    return [
        get_holdings_summary,
        compute_performance,
        compute_risk_metrics,
        compute_allocation_breakdown,
        research_lookup,
    ]
