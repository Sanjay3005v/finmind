from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PortfolioCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    base_currency: str = Field(default="INR", min_length=3, max_length=3)
    is_default: bool = False


class PortfolioResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    base_currency: str
    is_default: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class HoldingResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    broker_connection_id: Optional[UUID] = None
    symbol: str
    exchange: str
    quantity: float
    avg_price: float
    current_price: Optional[float] = None
    asset_class: str
    sector: Optional[str] = None
    currency: str
    updated_at: datetime
    # Computed via app/financial/allocation.py::position_pnl — never derived
    # ad hoc in the frontend, per the project's "no financial math outside
    # app/financial" rule.
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float

    model_config = {"from_attributes": True}


class HoldingCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    exchange: str = Field(default="NSE", min_length=1, max_length=20)
    quantity: float = Field(gt=0)
    avg_price: float = Field(gt=0)
    current_price: Optional[float] = Field(default=None, gt=0)
    asset_class: str = Field(default="equity")
    sector: Optional[str] = Field(default=None, max_length=100)
    currency: str = Field(default="INR", min_length=3, max_length=3)


class MoverItem(BaseModel):
    symbol: str
    asset_class: str
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float


class MoversResponse(BaseModel):
    portfolio_id: UUID
    gainers: list[MoverItem]
    losers: list[MoverItem]


class PriceRefreshFailure(BaseModel):
    symbol: str
    exchange: str
    error: str


class PriceRefreshResponse(BaseModel):
    portfolio_id: UUID
    updated: list[HoldingResponse]
    failed: list[PriceRefreshFailure]


class PriceHistoryPoint(BaseModel):
    date: str
    close: float
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    volume: Optional[float] = None


class PriceHistoryResponse(BaseModel):
    symbol: str
    exchange: str
    ticker: str
    currency: str
    points: list[PriceHistoryPoint]


class TransactionResponse(BaseModel):
    id: UUID
    portfolio_id: UUID
    symbol: str
    exchange: str
    side: str
    quantity: float
    price: float
    fees: float
    executed_at: datetime
    source: str
    broker_order_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedTransactions(BaseModel):
    items: list[TransactionResponse]
    limit: int
    offset: int
    total: int


class PerformanceResponse(BaseModel):
    portfolio_id: UUID
    range: str
    start_value: float
    end_value: float
    simple_return: Optional[float] = None
    cagr: Optional[float] = None
    annualized_volatility: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    sortino_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    equity_curve: list[float] = Field(default_factory=list)


class AllocationResponse(BaseModel):
    portfolio_id: UUID
    total_market_value: float
    by_asset_class: dict
    by_sector: dict
    concentration_score: float
