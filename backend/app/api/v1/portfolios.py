"""Portfolio CRUD + holdings/transactions/performance/allocation.

Performance note: this phase's schema has no historical daily-price table,
so `equity_curve` is built from the running book value (cumulative cost
basis) implied by `transactions`, not true daily mark-to-market. It is
deterministic and good enough for CAGR/volatility/Sharpe/max-drawdown at
this foundation stage; a later phase with a price-history table should
replace `_build_equity_curve` with real NAV series without touching the
`app/financial` functions themselves.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_owned_holding, get_owned_portfolio, parse_user_uuid
from app.core.errors import AppError
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.financial import (
    allocation_breakdown,
    annualized_volatility,
    cagr,
    concentration_score,
    max_drawdown,
    position_pnl,
    sharpe_ratio,
    sortino_ratio,
    top_movers,
)
from app.market_data import get_history, get_quotes, to_yahoo_ticker
from app.models.holding import ASSET_CLASSES, Holding
from app.models.portfolio import Portfolio
from app.models.transaction import Transaction
from app.schemas.portfolio import (
    AllocationResponse,
    HoldingCreateRequest,
    HoldingResponse,
    MoversResponse,
    PaginatedTransactions,
    PerformanceResponse,
    PortfolioCreateRequest,
    PortfolioResponse,
    PriceHistoryPoint,
    PriceHistoryResponse,
    PriceRefreshFailure,
    PriceRefreshResponse,
    TransactionResponse,
)

router = APIRouter(
    prefix="/portfolios", tags=["portfolios"], dependencies=[Depends(rate_limit_dependency)]
)

RANGE_TO_DAYS = {"1M": 30, "3M": 90, "1Y": 365, "ALL": None}


@router.get("", response_model=list[PortfolioResponse])
async def list_portfolios(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[Portfolio]:
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(
        select(Portfolio).where(Portfolio.user_id == owner_uuid).order_by(Portfolio.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=PortfolioResponse, status_code=201)
async def create_portfolio(
    payload: PortfolioCreateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Portfolio:
    owner_uuid = parse_user_uuid(user_id)
    portfolio = Portfolio(
        user_id=owner_uuid,
        name=payload.name,
        base_currency=payload.base_currency,
        is_default=payload.is_default,
    )
    db.add(portfolio)
    await db.flush()
    await db.refresh(portfolio)
    return portfolio


@router.get("/{id}", response_model=PortfolioResponse)
async def get_portfolio(portfolio: Portfolio = Depends(get_owned_portfolio)) -> Portfolio:
    return portfolio


def _to_holding_response(h: Holding) -> HoldingResponse:
    current_price = float(h.current_price) if h.current_price is not None else None
    pnl = position_pnl(float(h.quantity), float(h.avg_price), current_price)
    return HoldingResponse(
        id=h.id,
        portfolio_id=h.portfolio_id,
        broker_connection_id=h.broker_connection_id,
        symbol=h.symbol,
        exchange=h.exchange,
        quantity=float(h.quantity),
        avg_price=float(h.avg_price),
        current_price=current_price,
        asset_class=h.asset_class,
        sector=h.sector,
        currency=h.currency,
        updated_at=h.updated_at,
        **pnl,
    )


@router.get("/{id}/holdings", response_model=list[HoldingResponse])
async def list_holdings(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: AsyncSession = Depends(get_db),
) -> list[HoldingResponse]:
    result = await db.execute(
        select(Holding).where(Holding.portfolio_id == portfolio.id).order_by(Holding.symbol)
    )
    holdings = list(result.scalars().all())
    return [_to_holding_response(h) for h in holdings]


@router.post("/{id}/holdings", response_model=HoldingResponse, status_code=201)
async def create_holding(
    payload: HoldingCreateRequest,
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: AsyncSession = Depends(get_db),
) -> HoldingResponse:
    """Manually records a holding — the only way to track an asset that has
    no broker adapter (gold, silver, or any other instrument outside the
    four supported brokers). Symbol+exchange must be unique within the
    portfolio (matches `uq_holdings_portfolio_symbol`); adding one that
    already exists is a conflict, not a silent merge — broker sync updates
    existing rows through `broker_service.sync_holdings` instead, so a
    manual add always means "this is new"."""
    if payload.asset_class not in ASSET_CLASSES:
        raise AppError(
            code="INVALID_ASSET_CLASS", message=f"asset_class must be one of {ASSET_CLASSES}", status_code=422
        )

    existing = await db.execute(
        select(Holding).where(
            Holding.portfolio_id == portfolio.id,
            Holding.symbol == payload.symbol,
            Holding.exchange == payload.exchange,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AppError(
            code="HOLDING_ALREADY_EXISTS",
            message=f"{payload.symbol} on {payload.exchange} already exists in this portfolio.",
            status_code=409,
        )

    holding = Holding(
        portfolio_id=portfolio.id,
        symbol=payload.symbol.upper(),
        exchange=payload.exchange.upper(),
        quantity=payload.quantity,
        avg_price=payload.avg_price,
        current_price=payload.current_price,
        asset_class=payload.asset_class,
        sector=payload.sector,
        currency=payload.currency.upper(),
    )
    db.add(holding)
    await db.flush()
    await db.refresh(holding)
    return _to_holding_response(holding)


@router.delete("/{id}/holdings/{holding_id}", status_code=204)
async def delete_holding(holding: Holding = Depends(get_owned_holding), db: AsyncSession = Depends(get_db)) -> None:
    await db.delete(holding)
    await db.flush()


@router.post("/{id}/holdings/refresh-prices", response_model=PriceRefreshResponse)
async def refresh_holding_prices(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: AsyncSession = Depends(get_db),
) -> PriceRefreshResponse:
    """Pulls a real, live quote for every holding from Yahoo Finance
    (app/market_data) and updates `current_price` — this is the only path
    that keeps manually-added holdings (gold, silver, anything with no
    broker sync) priced with real market data instead of a stale one-time
    entry. A symbol Yahoo doesn't recognize is reported in `failed` rather
    than silently left unchanged or guessed."""
    result = await db.execute(select(Holding).where(Holding.portfolio_id == portfolio.id))
    holdings = list(result.scalars().all())
    if not holdings:
        return PriceRefreshResponse(portfolio_id=portfolio.id, updated=[], failed=[])

    quotes, failures = await get_quotes([(h.symbol, h.exchange) for h in holdings])
    quotes_by_key = {(q.symbol, q.exchange): q for q in quotes}

    updated: list[Holding] = []
    for h in holdings:
        quote = quotes_by_key.get((h.symbol, h.exchange))
        if quote is not None:
            h.current_price = quote.price
            updated.append(h)

    await db.flush()
    for h in updated:
        await db.refresh(h)

    return PriceRefreshResponse(
        portfolio_id=portfolio.id,
        updated=[_to_holding_response(h) for h in updated],
        failed=[PriceRefreshFailure(**f) for f in failures],
    )



@router.get("/{id}/holdings/{holding_id}/price-history", response_model=PriceHistoryResponse)
async def get_holding_price_history(
    holding: Holding = Depends(get_owned_holding),
    range: str = Query(default="1mo", alias="range", pattern="^(5d|1mo|3mo|6mo|1y|5y)$"),
) -> PriceHistoryResponse:
    """Real historical daily closes for this holding's symbol, straight
    from Yahoo Finance (app/market_data) — never derived from the
    portfolio's own transaction/book-value history, which is what
    `/performance`'s `equity_curve` does and is a different, coarser thing."""
    points = await get_history(holding.symbol, holding.exchange, range_=range)
    return PriceHistoryResponse(
        symbol=holding.symbol,
        exchange=holding.exchange,
        ticker=to_yahoo_ticker(holding.symbol, holding.exchange),
        currency=holding.currency,
        points=[
            PriceHistoryPoint(date=p.date, close=p.close, open=p.open, high=p.high, low=p.low, volume=p.volume)
            for p in points
        ],
    )


@router.get("/{id}/movers", response_model=MoversResponse)
async def get_movers(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=5, ge=1, le=20),
) -> MoversResponse:
    result = await db.execute(select(Holding).where(Holding.portfolio_id == portfolio.id))
    holdings = list(result.scalars().all())
    movers = top_movers(_holding_dicts(holdings), n=limit)
    return MoversResponse(portfolio_id=portfolio.id, gainers=movers["gainers"], losers=movers["losers"])


@router.get("/{id}/transactions", response_model=PaginatedTransactions)
async def list_transactions(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> PaginatedTransactions:
    base_query = select(Transaction).where(Transaction.portfolio_id == portfolio.id)

    total_result = await db.execute(
        select(func.count()).select_from(base_query.subquery())
    )
    total = total_result.scalar_one()

    result = await db.execute(
        base_query.order_by(Transaction.executed_at.desc()).limit(limit).offset(offset)
    )
    items = list(result.scalars().all())
    return PaginatedTransactions(items=items, limit=limit, offset=offset, total=total)


def _holding_dicts(holdings: list[Holding]) -> list[dict]:
    return [
        {
            "symbol": h.symbol,
            "asset_class": h.asset_class,
            "sector": h.sector,
            "quantity": float(h.quantity),
            "avg_price": float(h.avg_price),
            "current_price": float(h.current_price) if h.current_price is not None else None,
        }
        for h in holdings
    ]


def _current_market_value(holdings: list[Holding]) -> float:
    total = 0.0
    for h in holdings:
        price = h.current_price if h.current_price is not None else h.avg_price
        total += float(h.quantity) * float(price)
    return total


def _build_equity_curve(transactions: list[Transaction]) -> list[float]:
    """Cumulative running book value from chronological transactions.
    Buys add (price*qty + fees) to book value; sells remove it. See module
    docstring for why this stands in for a true price-based equity curve."""
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


@router.get("/{id}/performance", response_model=PerformanceResponse)
async def get_performance(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: AsyncSession = Depends(get_db),
    range: str = Query(default="ALL", alias="range", pattern="^(1M|3M|1Y|ALL)$"),
) -> PerformanceResponse:
    days = RANGE_TO_DAYS.get(range)
    tx_query = select(Transaction).where(Transaction.portfolio_id == portfolio.id)
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        tx_query = tx_query.where(Transaction.executed_at >= cutoff)
    tx_result = await db.execute(tx_query.order_by(Transaction.executed_at))
    transactions = list(tx_result.scalars().all())

    holdings_result = await db.execute(select(Holding).where(Holding.portfolio_id == portfolio.id))
    holdings = list(holdings_result.scalars().all())

    end_value = _current_market_value(holdings)
    equity_curve = _build_equity_curve(transactions)

    start_value = equity_curve[0] if equity_curve else 0.0
    simple_ret = None
    cagr_val = None
    vol = None
    sharpe = None
    sortino = None
    mdd = None

    if equity_curve and start_value > 0:
        simple_ret = (end_value - start_value) / start_value

        first_ts = transactions[0].executed_at
        last_ts = transactions[-1].executed_at
        years = max((last_ts - first_ts).days / 365.25, 1 / 365.25)
        try:
            cagr_val = cagr(start_value, end_value, years)
        except (ValueError, OverflowError):
            # A very short `years` (e.g. one transaction within the
            # requested range) combined with a large end/start ratio can
            # blow up the `** (1/years)` exponentiation past float range —
            # not a real CAGR, so treat it the same as any other
            # "can't compute this metric yet" case rather than 500ing.
            cagr_val = None

        # zip pairs, not range(...) — this function's `range` query param
        # (the "1M"/"3M"/"1Y"/"ALL" string) shadows the builtin `range()` in
        # this local scope, so range() would raise "'str' object is not
        # callable" the moment this branch actually executes.
        periodic_returns = [
            (curr - prev) / prev for prev, curr in zip(equity_curve, equity_curve[1:]) if prev > 0
        ]
        if len(periodic_returns) >= 2:
            try:
                vol = annualized_volatility(periodic_returns, periods_per_year=252)
            except ValueError:
                vol = None
            try:
                sharpe = sharpe_ratio(periodic_returns, periods_per_year=252)
            except ValueError:
                sharpe = None
            try:
                sortino = sortino_ratio(periodic_returns, periods_per_year=252)
            except ValueError:
                sortino = None

        full_curve = [start_value] + equity_curve + [end_value]
        if len(full_curve) >= 2:
            try:
                mdd = max_drawdown(full_curve)
            except ValueError:
                mdd = None

    return PerformanceResponse(
        portfolio_id=portfolio.id,
        range=range,
        start_value=start_value,
        end_value=end_value,
        simple_return=simple_ret,
        cagr=cagr_val,
        annualized_volatility=vol,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown=mdd,
        equity_curve=equity_curve,
    )


@router.get("/{id}/allocation", response_model=AllocationResponse)
async def get_allocation(
    portfolio: Portfolio = Depends(get_owned_portfolio),
    db: AsyncSession = Depends(get_db),
) -> AllocationResponse:
    result = await db.execute(select(Holding).where(Holding.portfolio_id == portfolio.id))
    holdings = list(result.scalars().all())
    holding_dicts = _holding_dicts(holdings)

    breakdown = allocation_breakdown(holding_dicts)
    score = concentration_score(holding_dicts)

    return AllocationResponse(
        portfolio_id=portfolio.id,
        total_market_value=breakdown["total_market_value"],
        by_asset_class=breakdown["by_asset_class"],
        by_sector=breakdown["by_sector"],
        concentration_score=score,
    )
