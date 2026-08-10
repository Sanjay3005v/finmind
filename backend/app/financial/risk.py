"""Risk calculations: volatility, Sharpe, Sortino, max drawdown, beta.

Pure functions, no I/O. Sample (n-1) variance is used throughout, matching
standard portfolio-analytics convention.
"""
from __future__ import annotations

import math
from typing import Sequence


def _mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs)


def _sample_variance(xs: Sequence[float]) -> float:
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)


def annualized_volatility(periodic_returns: Sequence[float], periods_per_year: int = 252) -> float:
    """Sample standard deviation of periodic returns, annualized by sqrt(periods_per_year)."""
    if len(periodic_returns) < 2:
        raise ValueError("annualized_volatility requires at least two periodic returns.")
    std = math.sqrt(_sample_variance(periodic_returns))
    return std * math.sqrt(periods_per_year)


def sharpe_ratio(
    periodic_returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sharpe ratio. `risk_free_rate` is an ANNUAL rate; it is
    converted to a per-period rate internally before computing excess returns."""
    if len(periodic_returns) < 2:
        raise ValueError("sharpe_ratio requires at least two periodic returns.")
    periodic_rf = risk_free_rate / periods_per_year
    excess = [r - periodic_rf for r in periodic_returns]
    mean_excess = _mean(excess)
    std = math.sqrt(_sample_variance(excess))
    if std == 0:
        raise ValueError("sharpe_ratio is undefined when excess-return volatility is zero.")
    return (mean_excess / std) * math.sqrt(periods_per_year)


def sortino_ratio(
    periodic_returns: Sequence[float],
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """Annualized Sortino ratio: excess return over downside deviation only."""
    if len(periodic_returns) < 2:
        raise ValueError("sortino_ratio requires at least two periodic returns.")
    periodic_rf = risk_free_rate / periods_per_year
    excess = [r - periodic_rf for r in periodic_returns]
    mean_excess = _mean(excess)
    downside = [min(0.0, r) for r in excess]
    downside_variance = sum(d**2 for d in downside) / len(excess)
    downside_deviation = math.sqrt(downside_variance)
    if downside_deviation == 0:
        raise ValueError("sortino_ratio is undefined when downside deviation is zero.")
    return (mean_excess / downside_deviation) * math.sqrt(periods_per_year)


def max_drawdown(equity_curve: Sequence[float]) -> float:
    """Largest peak-to-trough decline, expressed as a negative fraction
    (e.g. -0.25 for a 25% drawdown). 0.0 if the curve never declines."""
    if len(equity_curve) < 2:
        raise ValueError("max_drawdown requires at least two points in the equity curve.")
    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        if value > peak:
            peak = value
        if peak > 0:
            drawdown = (value - peak) / peak
            if drawdown < worst:
                worst = drawdown
    return worst


def beta(asset_returns: Sequence[float], benchmark_returns: Sequence[float]) -> float:
    """Covariance(asset, benchmark) / Variance(benchmark)."""
    if len(asset_returns) != len(benchmark_returns):
        raise ValueError("asset_returns and benchmark_returns must be the same length.")
    if len(asset_returns) < 2:
        raise ValueError("beta requires at least two paired observations.")
    mean_a = _mean(asset_returns)
    mean_b = _mean(benchmark_returns)
    n = len(asset_returns)
    covariance = sum((a - mean_a) * (b - mean_b) for a, b in zip(asset_returns, benchmark_returns)) / (n - 1)
    variance_b = _sample_variance(benchmark_returns)
    if variance_b == 0:
        raise ValueError("beta is undefined when benchmark variance is zero.")
    return covariance / variance_b
