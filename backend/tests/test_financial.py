"""Hand-computed expected values for app/financial — pure, no DB/network needed."""
from datetime import date

import pytest

from app.financial import (
    allocation_breakdown,
    annualized_volatility,
    beta,
    cagr,
    concentration_score,
    max_drawdown,
    sharpe_ratio,
    simple_return,
    sortino_ratio,
    top_movers,
    xirr,
)


def test_simple_return_basic():
    # (120 - 100) / 100 = 0.20
    assert simple_return(100, 120) == pytest.approx(0.20)


def test_simple_return_loss():
    assert simple_return(200, 150) == pytest.approx(-0.25)


def test_simple_return_zero_start_raises():
    with pytest.raises(ValueError):
        simple_return(0, 100)


def test_cagr_two_point_doubling_over_two_years():
    # (200/100)^(1/2) - 1 = sqrt(2) - 1
    assert cagr(100, 200, 2) == pytest.approx(2**0.5 - 1, rel=1e-9)


def test_cagr_flat_is_zero():
    assert cagr(100, 100, 5) == pytest.approx(0.0)


def test_cagr_extreme_ratio_over_tiny_years_overflows():
    # A real trigger: a portfolio with one transaction executed seconds ago
    # (years ~= 1/365.25, the floor `get_performance` applies) next to a
    # much larger current total market value (from other, transaction-less
    # broker-synced holdings) blows `** (1/years)` past float range. The
    # caller (app/api/v1/portfolios.py::get_performance) must catch
    # OverflowError alongside ValueError rather than 500ing — this pins the
    # exact exception type so that catch doesn't silently stop matching.
    with pytest.raises(OverflowError):
        cagr(15000, 150000, 1 / 365.25)


def test_cagr_invalid_years_raises():
    with pytest.raises(ValueError):
        cagr(100, 120, 0)


def test_xirr_excel_textbook_example():
    # Classic Excel XIRR help example; documented answer is ~37.3362535%.
    cashflows = [
        (date(2008, 1, 1), -10000.0),
        (date(2008, 3, 1), 2750.0),
        (date(2008, 10, 30), 4250.0),
        (date(2009, 2, 15), 3250.0),
        (date(2009, 4, 1), 2750.0),
    ]
    result = xirr(cashflows)
    assert result == pytest.approx(0.373362535, rel=1e-4)


def test_xirr_simple_single_period_matches_simple_return():
    # A single buy + single sell exactly one year apart should match a plain
    # (end/start - 1) return, since XIRR degenerates to that case.
    cashflows = [(date(2023, 1, 1), -1000.0), (date(2024, 1, 1), 1100.0)]
    result = xirr(cashflows)
    assert result == pytest.approx(0.10, rel=1e-3)


def test_xirr_requires_mixed_signs():
    with pytest.raises(ValueError):
        xirr([(date(2023, 1, 1), 100.0), (date(2023, 6, 1), 200.0)])


def test_xirr_requires_two_cashflows():
    with pytest.raises(ValueError):
        xirr([(date(2023, 1, 1), -100.0)])


def test_annualized_volatility_hand_computed():
    # returns = [0.02, -0.02] -> sample std = sqrt(0.0008) ; annualized with
    # periods_per_year=2 gives exactly sqrt(0.0008) * sqrt(2) = sqrt(0.0016) = 0.04
    assert annualized_volatility([0.02, -0.02], periods_per_year=2) == pytest.approx(0.04, rel=1e-9)


def test_annualized_volatility_requires_two_points():
    with pytest.raises(ValueError):
        annualized_volatility([0.01])


def test_sharpe_ratio_hand_computed():
    # returns = [0.03, 0.01], rf=0, ppy=2 -> mean=0.02, std=sqrt(0.0002)
    # sharpe = (0.02/std)*sqrt(2) = 2.0 exactly.
    assert sharpe_ratio([0.03, 0.01], risk_free_rate=0.0, periods_per_year=2) == pytest.approx(2.0, rel=1e-9)


def test_sortino_ratio_hand_computed():
    # returns = [0.05, -0.03], rf=0, ppy=2 -> downside deviation only from -0.03
    # sortino works out to exactly 2/3 (see app/financial/risk.py docstring math).
    assert sortino_ratio([0.05, -0.03], risk_free_rate=0.0, periods_per_year=2) == pytest.approx(2 / 3, rel=1e-9)


def test_sortino_ratio_undefined_when_no_downside():
    with pytest.raises(ValueError):
        sortino_ratio([0.01, 0.02], risk_free_rate=0.0, periods_per_year=2)


def test_max_drawdown_synthetic_curve():
    # peak sequence: 100 -> 120 -> (dip to 90, dd=-0.25) -> 130 (new peak)
    # -> (dip to 60, dd = (60-130)/130 = -0.53846...) -> 140
    curve = [100, 120, 90, 130, 60, 140]
    assert max_drawdown(curve) == pytest.approx(-70 / 130, rel=1e-9)


def test_max_drawdown_never_declines():
    assert max_drawdown([100, 110, 120, 130]) == pytest.approx(0.0)


def test_beta_perfect_linear_scale():
    # asset_returns are exactly 2x benchmark_returns -> beta must be exactly 2.
    asset = [0.02, 0.04, -0.01]
    benchmark = [0.01, 0.02, -0.005]
    assert beta(asset, benchmark) == pytest.approx(2.0, rel=1e-9)


def test_beta_zero_benchmark_variance_raises():
    with pytest.raises(ValueError):
        beta([0.01, 0.02, 0.03], [0.01, 0.01, 0.01])


def _sample_holdings():
    return [
        {"symbol": "A", "asset_class": "equity", "sector": "tech", "quantity": 10, "current_price": 100},
        {"symbol": "B", "asset_class": "equity", "sector": "finance", "quantity": 5, "current_price": 200},
        {"symbol": "C", "asset_class": "bond", "sector": "gov", "quantity": 100, "current_price": 10},
    ]


def test_allocation_breakdown_hand_computed():
    # Market values: A=1000, B=1000, C=1000 -> total=3000
    # by_asset_class: equity=2000 (66.6667%), bond=1000 (33.3333%)
    # by_sector: tech/finance/gov each 1000 (33.3333%)
    result = allocation_breakdown(_sample_holdings())
    assert result["total_market_value"] == pytest.approx(3000.0)
    assert result["by_asset_class"]["percentage"]["equity"] == pytest.approx(66.6667, rel=1e-3)
    assert result["by_asset_class"]["percentage"]["bond"] == pytest.approx(33.3333, rel=1e-3)
    assert result["by_sector"]["percentage"]["tech"] == pytest.approx(33.3333, rel=1e-3)
    assert result["by_sector"]["percentage"]["finance"] == pytest.approx(33.3333, rel=1e-3)
    assert result["by_sector"]["percentage"]["gov"] == pytest.approx(33.3333, rel=1e-3)


def test_allocation_breakdown_empty_portfolio():
    result = allocation_breakdown([])
    assert result["total_market_value"] == 0
    assert result["by_asset_class"]["percentage"] == {}


def test_concentration_score_hand_computed():
    # Three equal-weight (1/3 each) positions -> HHI = 3 * (1/3)^2 = 1/3.
    assert concentration_score(_sample_holdings()) == pytest.approx(1 / 3, rel=1e-6)


def test_concentration_score_single_position_is_one():
    holdings = [{"symbol": "A", "quantity": 10, "current_price": 100, "asset_class": "equity", "sector": "tech"}]
    assert concentration_score(holdings) == pytest.approx(1.0)


def test_concentration_score_empty_is_zero():
    assert concentration_score([]) == 0.0


def _movers_holdings():
    return [
        # +50%
        {"symbol": "GOLD", "asset_class": "commodity", "quantity": 10, "avg_price": 100, "current_price": 150},
        # -20%
        {"symbol": "SILVER", "asset_class": "commodity", "quantity": 10, "avg_price": 100, "current_price": 80},
        # +10%
        {"symbol": "TCS", "asset_class": "equity", "quantity": 5, "avg_price": 1000, "current_price": 1100},
    ]


def test_top_movers_ranks_by_pnl_percent():
    result = top_movers(_movers_holdings(), n=2)
    assert [g["symbol"] for g in result["gainers"]] == ["GOLD", "TCS"]
    assert result["gainers"][0]["unrealized_pnl_percent"] == pytest.approx(50.0)
    assert [l["symbol"] for l in result["losers"]] == ["SILVER", "TCS"]
    assert result["losers"][0]["unrealized_pnl_percent"] == pytest.approx(-20.0)


def test_top_movers_empty_portfolio():
    result = top_movers([], n=5)
    assert result == {"gainers": [], "losers": []}
