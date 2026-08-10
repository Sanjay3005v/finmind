import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.db.session import Base

ASSET_CLASSES = ("equity", "etf", "mutual_fund", "bond", "cash", "commodity", "crypto")


class Holding(Base):
    __tablename__ = "holdings"
    __table_args__ = (
        CheckConstraint(f"asset_class in {ASSET_CLASSES!r}", name="ck_holdings_asset_class"),
        Index("idx_holdings_portfolio", "portfolio_id"),
        UniqueConstraint("portfolio_id", "symbol", "exchange", name="uq_holdings_portfolio_symbol"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("broker_connections.id", ondelete="SET NULL"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str] = mapped_column(Text, nullable=False, default="NSE", server_default="NSE")
    quantity: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    avg_price: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    current_price: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    asset_class: Mapped[str] = mapped_column(Text, nullable=False, default="equity", server_default="equity")
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="INR", server_default="INR")
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
