import uuid

from sqlalchemy import ForeignKey, Index, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.db.session import Base


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    __table_args__ = (Index("idx_risk_portfolio", "portfolio_id", "computed_at"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    volatility_annual: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    sortino_ratio: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    beta: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    var_95: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    concentration_score: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    computed_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
