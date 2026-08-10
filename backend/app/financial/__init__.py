"""Deterministic financial calculation tools.

Pure Python, no I/O, no LLM calls. These are the ONLY functions allowed to
compute returns/risk/valuation numbers anywhere in the codebase — agents
(added in a later phase) call these as tools and only narrate the results.
"""
from app.financial.allocation import allocation_breakdown, concentration_score, position_pnl, top_movers
from app.financial.returns import cagr, simple_return, xirr
from app.financial.risk import (
    annualized_volatility,
    beta,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)

__all__ = [
    "simple_return",
    "cagr",
    "xirr",
    "annualized_volatility",
    "sharpe_ratio",
    "sortino_ratio",
    "max_drawdown",
    "beta",
    "allocation_breakdown",
    "concentration_score",
    "position_pnl",
    "top_movers",
]
