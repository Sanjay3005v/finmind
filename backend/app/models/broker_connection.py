import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, LargeBinary, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.db.session import Base

BROKERS = ("dhan", "angelone", "upstox", "fyers")
MODES = ("paper", "live")
STATUSES = ("disconnected", "connected", "error", "expired")


class BrokerConnection(Base):
    __tablename__ = "broker_connections"
    __table_args__ = (
        CheckConstraint(f"broker in {BROKERS!r}", name="ck_broker_connections_broker"),
        CheckConstraint(f"mode in {MODES!r}", name="ck_broker_connections_mode"),
        CheckConstraint(f"status in {STATUSES!r}", name="ck_broker_connections_status"),
        Index("idx_broker_conn_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    broker: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="paper", server_default="paper")
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="disconnected", server_default="disconnected"
    )
    # App-level AES-GCM envelope; never plaintext.
    encrypted_credentials: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    label: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_synced_at: Mapped[object | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
