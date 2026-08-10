import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.db.session import Base

STATUSES = ("queued", "running", "ready", "error")


class ReportJob(Base):
    """A generated report. Content is never persisted here — it's
    regenerated on every download from the same deterministic
    performance/allocation functions the API uses live, so a downloaded
    report always reflects current data rather than a stale snapshot taken
    at generate time."""

    __tablename__ = "report_jobs"
    __table_args__ = (
        CheckConstraint(f"status in {STATUSES!r}", name="ck_report_jobs_status"),
        Index("idx_report_jobs_user", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ready", server_default="ready")
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
