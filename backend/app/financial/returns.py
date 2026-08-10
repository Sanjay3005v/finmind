"""Return calculations: simple return, CAGR, XIRR.

Pure functions, no I/O. `xirr` uses Newton-Raphson with a bisection fallback
on non-convergence (raises `ValueError` if neither converges).
"""
from __future__ import annotations

from datetime import date
from typing import Sequence


def simple_return(start_value: float, end_value: float) -> float:
    """(end - start) / start."""
    if start_value == 0:
        raise ValueError("start_value must be non-zero to compute a simple return.")
    return (end_value - start_value) / start_value


def cagr(start_value: float, end_value: float, years: float) -> float:
    """Compound annual growth rate: (end/start)^(1/years) - 1."""
    if start_value <= 0:
        raise ValueError("start_value must be positive to compute CAGR.")
    if end_value < 0:
        raise ValueError("end_value cannot be negative.")
    if years <= 0:
        raise ValueError("years must be positive.")
    return (end_value / start_value) ** (1.0 / years) - 1.0


def _xnpv(rate: float, cashflows: Sequence[tuple[date, float]]) -> float:
    t0 = cashflows[0][0]
    return sum(cf / (1.0 + rate) ** ((d - t0).days / 365.0) for d, cf in cashflows)


def _xnpv_derivative(rate: float, cashflows: Sequence[tuple[date, float]]) -> float:
    t0 = cashflows[0][0]
    total = 0.0
    for d, cf in cashflows:
        t = (d - t0).days / 365.0
        if t == 0:
            continue
        total += -t * cf / (1.0 + rate) ** (t + 1)
    return total


def xirr(
    cashflows: list[tuple[date, float]],
    guess: float = 0.1,
    tol: float = 1e-7,
    max_iterations: int = 100,
) -> float:
    """Internal rate of return for irregularly-dated cashflows.

    `cashflows` is a list of (date, amount) tuples; amounts must include at
    least one negative (outflow) and one positive (inflow) value. Solves
    NPV(rate) = 0 via Newton-Raphson, falling back to bisection over
    [-0.999999, 10.0] if Newton-Raphson fails to converge. Raises
    `ValueError` if neither method converges.
    """
    if len(cashflows) < 2:
        raise ValueError("xirr requires at least two cashflows.")
    ordered = sorted(cashflows, key=lambda cf: cf[0])
    amounts = [cf for _, cf in ordered]
    if not any(a > 0 for a in amounts) or not any(a < 0 for a in amounts):
        raise ValueError("xirr requires at least one positive and one negative cashflow.")

    rate = guess
    for _ in range(max_iterations):
        npv = _xnpv(rate, ordered)
        if abs(npv) < tol:
            return rate
        deriv = _xnpv_derivative(rate, ordered)
        if deriv == 0:
            break
        new_rate = rate - npv / deriv
        if new_rate <= -0.999999:
            new_rate = (rate - 0.999999) / 2
        if abs(new_rate - rate) < tol:
            rate = new_rate
            npv = _xnpv(rate, ordered)
            if abs(npv) < 1e-4:
                return rate
            break
        rate = new_rate
    else:
        npv = _xnpv(rate, ordered)
        if abs(npv) < 1e-4:
            return rate

    # Fallback: bisection over a wide, economically sane bracket.
    low, high = -0.999999, 10.0
    f_low = _xnpv(low, ordered)
    f_high = _xnpv(high, ordered)
    if f_low * f_high > 0:
        raise ValueError(
            "xirr failed to converge: no sign change found for rate in [-99.9999%, 1000%]."
        )
    for _ in range(200):
        mid = (low + high) / 2
        f_mid = _xnpv(mid, ordered)
        if abs(f_mid) < tol or (high - low) < tol:
            return mid
        if f_low * f_mid < 0:
            high, f_high = mid, f_mid
        else:
            low, f_low = mid, f_mid

    raise ValueError("xirr failed to converge after Newton-Raphson and bisection fallback.")
