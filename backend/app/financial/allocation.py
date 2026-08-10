"""Allocation breakdown + concentration (HHI) over a list of holding dicts.

Each holding dict is expected to look like a row from `holdings`:
`{"symbol", "asset_class", "sector", "quantity", "avg_price", "current_price"}`.
Market value = quantity * (current_price if set else avg_price).
"""
from __future__ import annotations

from typing import Sequence


def position_pnl(quantity: float, avg_price: float, current_price: float | None) -> dict:
    """Per-position market value and unrealized P&L. Falls back to `avg_price`
    when no live `current_price` is known yet (fresh/never-repriced holding),
    in which case unrealized P&L is exactly zero rather than misleadingly
    undefined."""
    price = current_price if current_price is not None else avg_price
    market_value = float(quantity) * float(price)
    cost_basis = float(quantity) * float(avg_price)
    unrealized_pnl = market_value - cost_basis
    unrealized_pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0
    return {
        "market_value": round(market_value, 4),
        "unrealized_pnl": round(unrealized_pnl, 4),
        "unrealized_pnl_percent": round(unrealized_pnl_percent, 4),
    }


def _market_value(holding: dict) -> float:
    quantity = float(holding.get("quantity") or 0)
    price = holding.get("current_price")
    if price is None:
        price = holding.get("avg_price", 0)
    return quantity * float(price or 0)


def allocation_breakdown(holdings: Sequence[dict]) -> dict:
    """Groups market value by `asset_class` and by `sector`, returning both
    absolute totals and percentages of the portfolio's total market value."""
    total = sum(_market_value(h) for h in holdings)

    by_asset_class: dict[str, float] = {}
    by_sector: dict[str, float] = {}
    for h in holdings:
        mv = _market_value(h)
        asset_class = h.get("asset_class") or "unknown"
        sector = h.get("sector") or "unknown"
        by_asset_class[asset_class] = by_asset_class.get(asset_class, 0.0) + mv
        by_sector[sector] = by_sector.get(sector, 0.0) + mv

    def _pct(bucket: dict[str, float]) -> dict[str, float]:
        if total <= 0:
            return {k: 0.0 for k in bucket}
        return {k: round((v / total) * 100, 4) for k, v in bucket.items()}

    return {
        "total_market_value": round(total, 4),
        "by_asset_class": {
            "market_value": {k: round(v, 4) for k, v in by_asset_class.items()},
            "percentage": _pct(by_asset_class),
        },
        "by_sector": {
            "market_value": {k: round(v, 4) for k, v in by_sector.items()},
            "percentage": _pct(by_sector),
        },
    }


def top_movers(holdings: Sequence[dict], n: int = 5) -> dict:
    """Ranks holdings by unrealized P&L% (via `position_pnl`, the same
    per-position calculation the holdings endpoint uses — never recomputed
    ad hoc). Returns the top `n` gainers (highest %) and top `n` losers
    (lowest %), each holding annotated with its computed P&L fields."""
    annotated = []
    for h in holdings:
        pnl = position_pnl(
            float(h.get("quantity") or 0), float(h.get("avg_price") or 0), h.get("current_price")
        )
        annotated.append(
            {
                "symbol": h.get("symbol"),
                "asset_class": h.get("asset_class") or "unknown",
                **pnl,
            }
        )
    ranked = sorted(annotated, key=lambda a: a["unrealized_pnl_percent"], reverse=True)
    return {
        "gainers": ranked[:n],
        "losers": list(reversed(ranked[-n:])) if ranked else [],
    }


def concentration_score(holdings: Sequence[dict]) -> float:
    """Herfindahl-Hirschman index on position-weight fractions, naturally
    normalized to [1/n, 1] (1.0 = a single position holds the whole portfolio).
    Returns 0.0 for an empty portfolio or zero total market value.
    """
    total = sum(_market_value(h) for h in holdings)
    if total <= 0:
        return 0.0
    weights = [_market_value(h) / total for h in holdings if _market_value(h) > 0]
    hhi = sum(w**2 for w in weights)
    return round(hhi, 6)
