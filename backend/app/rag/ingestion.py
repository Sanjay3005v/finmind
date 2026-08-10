"""Document ingestion: extract text -> chunk -> embed -> persist chunks ->
flip document status to a terminal state.

NOTE: runs synchronously inline with the upload request for now. A later
phase should move this behind a Celery task (see docs/ARCHITECTURE.md's
`workers/` module and the identical deferred-async note on
`app/services/broker_service.py::sync_holdings`) so a large PDF / slow
embeddings call doesn't block the HTTP request.
"""
from __future__ import annotations

import io
from uuid import UUID

import structlog
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.rag.chunking import chunk_text
from app.rag.embeddings import embed_texts

logger = structlog.get_logger(__name__)

# OpenAI's embeddings endpoint accepts an array `input` — batch a
# conservative number of chunks per call rather than one-chunk-per-request
# or an unbounded single request.
EMBEDDING_BATCH_SIZE = 100
SUPPORTED_CONTENT_TYPES = {"text/plain", "application/pdf"}


def extract_text(file_bytes: bytes, content_type: str) -> str:
    """Extracts plain text from an uploaded file. Raises `AppError` for
    unsupported content types or unparseable files — never returns a
    silently-empty/garbage string for a file it couldn't actually read."""
    if content_type == "text/plain":
        return file_bytes.decode("utf-8", errors="replace")

    if content_type == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
        except Exception as exc:  # noqa: BLE001 — pypdf raises various error types
            raise AppError(
                code="DOCUMENT_PARSE_FAILED", message=f"Could not parse PDF: {exc}", status_code=400
            ) from exc

        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:  # noqa: BLE001 — one bad page shouldn't fail the whole document
                logger.warning("pdf_page_extract_failed")
                continue
        return "\n\n".join(pages)

    raise AppError(
        code="UNSUPPORTED_CONTENT_TYPE",
        message=f"Unsupported content type: {content_type!r}. Supported: {sorted(SUPPORTED_CONTENT_TYPES)}",
        status_code=400,
    )


async def _get_document(db: AsyncSession, document_id: UUID) -> Document:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise AppError(code="DOCUMENT_NOT_FOUND", message="Document not found.", status_code=404)
    return document


async def ingest_document(document_id: UUID, file_bytes: bytes, content_type: str, db: AsyncSession) -> int:
    """Extracts, chunks, embeds, and persists `document_chunks` rows for
    `document_id`. Always leaves `documents.status` in a terminal state
    ('ready' or 'failed') — never silently stuck at 'processing', even if
    extraction, chunking, or embedding raises. Returns the number of chunks
    written (0 on failure or if the document produced no chunks)."""
    document = await _get_document(db, document_id)
    document.status = "processing"
    await db.flush()

    try:
        text = extract_text(file_bytes, content_type)
        chunks = chunk_text(text)

        if not chunks:
            document.status = "ready"
            await db.flush()
            return 0

        vectors: list[list[float]] = []
        for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[start : start + EMBEDDING_BATCH_SIZE]
            vectors.extend(await embed_texts(batch))

        for idx, (chunk_content, vector) in enumerate(zip(chunks, vectors)):
            db.add(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=idx,
                    content=chunk_content,
                    embedding=vector,
                )
            )

        document.status = "ready"
        await db.flush()
        return len(chunks)
    except Exception as exc:  # noqa: BLE001 — ingestion must never leave status stuck at 'processing'
        logger.error(
            "document_ingestion_failed", document_id=str(document_id), error=str(exc), exc_info=True
        )
        document.status = "failed"
        await db.flush()
        return 0
