import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.db.session import Base

SIDES = ("buy", "sell")
ORDER_TYPES = ("market", "limit")
STATUSES = ("pending", "approved", "rejected", "expired", "executed", "failed")
REQUESTED_BY = ("agent", "user")


class TradeApproval(Base):
    __tablename__ = "trade_approvals"
    __table_args__ = (
        CheckConstraint(f"side in {SIDES!r}", name="ck_trade_approvals_side"),
        CheckConstraint(f"order_type in {ORDER_TYPES!r}", name="ck_trade_approvals_order_type"),
        CheckConstraint(f"status in {STATUSES!r}", name="ck_trade_approvals_status"),
        CheckConstraint(f"requested_by in {REQUESTED_BY!r}", name="ck_trade_approvals_requested_by"),
        Index("idx_trade_approvals_user", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_sessions.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    broker_connection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("broker_connections.id", ondelete="SET NULL"), nullable=True
    )
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    exchange: Mapped[str] = mapped_column(Text, nullable=False, default="NSE", server_default="NSE")
    side: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    order_type: Mapped[str] = mapped_column(Text, nullable=False, default="market", server_default="market")
    limit_price: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default="pending")
    requested_by: Mapped[str] = mapped_column(Text, nullable=False, default="agent", server_default="agent")
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_checks: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    broker_order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
