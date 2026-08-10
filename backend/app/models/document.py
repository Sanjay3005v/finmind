import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DateTime

from app.db.session import Base

SOURCE_TYPES = ("filing", "report", "news", "manual_upload")
STATUSES = ("pending", "processing", "ready", "failed")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(f"source_type in {SOURCE_TYPES!r}", name="ck_documents_source_type"),
        CheckConstraint(f"status in {STATUSES!r}", name="ck_documents_status"),
        Index("idx_documents_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # null = global/shared corpus
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="manual_upload", server_default="manual_upload"
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    storage_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default="pending")
    uploaded_at: Mapped[object] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
