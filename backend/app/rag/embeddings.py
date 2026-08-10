"""Thin wrapper around OpenAI's real `/v1/embeddings` endpoint.

No simulated/fabricated vectors: every call is a real HTTPS request via
`httpx.AsyncClient`. Any failure (network error, non-2xx response,
malformed body, mismatched vector count) raises `AppError("EMBEDDING_FAILED")`
rather than silently returning zeros/garbage — callers must handle the
error explicitly (e.g. `app/rag/ingestion.py` marks the document 'failed').
"""
from __future__ import annotations

import httpx
import structlog

from app.core.config import get_settings
from app.core.errors import AppError

logger = structlog.get_logger(__name__)

OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"
_TIMEOUT_SECONDS = 30.0


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embeds `texts` via a single OpenAI API call and returns one vector
    per input, in the same order as `texts`. Callers that need to embed
    more than ~100 texts should batch themselves before calling this (see
    `app/rag/ingestion.py::EMBEDDING_BATCH_SIZE`) — this function issues
    exactly one HTTP request per call, no internal chunking."""
    if not texts:
        return []

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise AppError(
            code="EMBEDDING_FAILED",
            message="OPENAI_API_KEY is not configured.",
            status_code=500,
        )

    payload = {"model": settings.EMBEDDING_MODEL, "input": texts}
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(OPENAI_EMBEDDINGS_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.error("embedding_request_failed", error=str(exc))
        raise AppError(
            code="EMBEDDING_FAILED", message="Failed to reach the embeddings API.", status_code=502
        ) from exc

    if response.status_code != 200:
        logger.error("embedding_api_error", status_code=response.status_code, body=response.text[:500])
        raise AppError(
            code="EMBEDDING_FAILED",
            message=f"Embeddings API returned status {response.status_code}.",
            status_code=502,
        )

    try:
        body = response.json()
        data = body["data"]
        # OpenAI already returns items in input order, but each item also
        # carries its own `index` — sort defensively so a batch's vector
        # order is always guaranteed to match `texts`' order.
        ordered = sorted(data, key=lambda item: item["index"])
        vectors = [item["embedding"] for item in ordered]
    except (KeyError, TypeError, ValueError) as exc:
        logger.error("embedding_response_malformed", error=str(exc))
        raise AppError(
            code="EMBEDDING_FAILED", message="Malformed embeddings API response.", status_code=502
        ) from exc

    if len(vectors) != len(texts):
        raise AppError(
            code="EMBEDDING_FAILED",
            message="Embeddings API returned a different number of vectors than inputs.",
            status_code=502,
        )
    return vectors
