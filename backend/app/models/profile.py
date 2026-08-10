import uuid

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text as sql_text
from sqlalchemy.types import DateTime

from app.db.session import Base

RISK_TOLERANCES = ("conservative", "moderate", "aggressive")


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(f"risk_tolerance in {RISK_TOLERANCES!r}", name="ck_profiles_risk_tolerance"),
    )

    # References auth.users(id) — the Supabase-managed auth schema, which is
    # not modeled locally (owned by Supabase Auth, not our migrations).
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), primary_key=True
    )
    full_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_tolerance: Mapped[str] = mapped_column(Text, nullable=False, default="moderate", server_default="moderate")
    investment_horizon_years: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    base_currency: Mapped[str] = mapped_column(Text, nullable=False, default="INR", server_default="INR")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
