"""Document upload + management (RAG corpus).

NOTE: `upload_document` runs `ingest_document` synchronously, inline with
the request, for now. A later phase should move this behind a Celery task
(see docs/ARCHITECTURE.md's `workers/` module) — same deferred-async note
as `app/services/broker_service.py::sync_holdings` — so a large PDF/slow
embeddings call doesn't block the HTTP request.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_owned_document, get_visible_document, parse_user_uuid
from app.core.errors import AppError
from app.core.rate_limit import rate_limit_dependency
from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.document import SOURCE_TYPES, Document
from app.rag.ingestion import ingest_document
from app.schemas.document import DocumentResponse

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(rate_limit_dependency)])


@router.get("", response_model=list[DocumentResponse])
async def list_documents(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    """Lists documents visible to the caller: their own uploads plus the
    shared/global corpus (`user_id IS NULL`) — matching the RLS policy
    semantics in docs/DATABASE_SCHEMA.sql."""
    owner_uuid = parse_user_uuid(user_id)
    result = await db.execute(
        select(Document)
        .where(or_(Document.user_id == owner_uuid, Document.user_id.is_(None)))
        .order_by(Document.uploaded_at.desc())
    )
    return list(result.scalars().all())


@router.post("", response_model=DocumentResponse, status_code=201)
async def upload_document(
    title: str = Form(...),
    source_type: str = Form(default="manual_upload"),
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Document:
    owner_uuid = parse_user_uuid(user_id)
    if source_type not in SOURCE_TYPES:
        raise AppError(
            code="INVALID_SOURCE_TYPE", message=f"source_type must be one of {SOURCE_TYPES}", status_code=422
        )

    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"

    document = Document(user_id=owner_uuid, title=title, source_type=source_type, status="pending")
    db.add(document)
    await db.flush()
    await db.refresh(document)

    # `ingest_document` never raises — it always leaves `document.status` in
    # a terminal state ('ready' or 'failed'), so the response below always
    # reflects the true final status of this upload.
    await ingest_document(document.id, file_bytes, content_type, db)
    await db.refresh(document)
    return document


@router.get("/{id}", response_model=DocumentResponse)
async def get_document(document: Document = Depends(get_visible_document)) -> Document:
    return document


@router.delete("/{id}", status_code=204)
async def delete_document(
    document: Document = Depends(get_owned_document),
    db: AsyncSession = Depends(get_db),
) -> None:
    # ON DELETE CASCADE (docs/DATABASE_SCHEMA.sql) removes the document's
    # chunks automatically.
    await db.delete(document)
    await db.flush()
