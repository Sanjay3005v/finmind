"""Research query orchestration: hybrid_search -> rerank -> cited synthesis.

Hard rule (docs/ARCHITECTURE.md section 7): the synthesis LLM call may only
answer from the chunks it was actually handed and must cite every claim
with a `[n]` marker mapped back to real `document_chunks` rows. We only
ever report a citation for a marker that actually appears in the model's
answer text — never a citation for a chunk that wasn't cited, and never one
that wasn't actually retrieved (markers outside the handed-in range are
dropped, see `_extract_citations`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.rag.rerank import DEFAULT_TOP_N, rerank
from app.rag.retrieval import DEFAULT_TOP_K, RetrievedChunk, hybrid_search

logger = structlog.get_logger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
SYNTHESIS_MODEL = "gpt-4.1-mini"
_TIMEOUT_SECONDS = 30.0
_CITATION_PATTERN = re.compile(r"\[(\d+)\]")

_SYSTEM_PROMPT = (
    "You are FINMIND's research assistant. Answer the user's question using "
    "ONLY the numbered source passages provided below — never use outside "
    "knowledge. Cite the source of every factual claim with its bracketed "
    "number, e.g. [1], immediately after the claim. If the provided passages "
    "do not contain enough information to answer the question, say so "
    "explicitly and answer only the part you can support with a citation, "
    "rather than guessing or filling gaps with unsupported claims."
)


@dataclass
class Citation:
    marker: int
    document_id: str
    document_title: str
    chunk_id: str
    chunk_index: int
    snippet: str


@dataclass
class ResearchAnswer:
    answer: str
    citations: list[Citation]


def _build_context(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for idx, chunk in enumerate(chunks, start=1):
        parts.append(f"[{idx}] (source: {chunk.document_title})\n{chunk.content}")
    return "\n\n".join(parts)


async def _synthesize(query: str, chunks: list[RetrievedChunk]) -> str:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise AppError(
            code="RESEARCH_LLM_UNAVAILABLE", message="OPENAI_API_KEY is not configured.", status_code=500
        )

    context = _build_context(chunks)
    payload = {
        "model": SYNTHESIS_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": f"Sources:\n{context}\n\nQuestion: {query}"},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(OPENAI_CHAT_URL, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.error("research_synthesis_request_failed", error=str(exc))
        raise AppError(
            code="RESEARCH_LLM_FAILED", message="Failed to reach the chat completions API.", status_code=502
        ) from exc

    if response.status_code != 200:
        logger.error("research_synthesis_api_error", status_code=response.status_code, body=response.text[:500])
        raise AppError(
            code="RESEARCH_LLM_FAILED",
            message=f"Chat completions API returned status {response.status_code}.",
            status_code=502,
        )

    try:
        return response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise AppError(
            code="RESEARCH_LLM_FAILED", message="Malformed chat completions response.", status_code=502
        ) from exc


def _extract_citations(answer: str, chunks: list[RetrievedChunk]) -> list[Citation]:
    """Parses `[n]` markers that actually appear in `answer` and maps them
    back to the chunks that were actually handed to the model. Markers
    outside the range of `chunks` (the model hallucinating a number) are
    silently dropped — we never fabricate a citation to a chunk that wasn't
    retrieved."""
    cited_markers = sorted({int(m) for m in _CITATION_PATTERN.findall(answer)})
    citations: list[Citation] = []
    for marker in cited_markers:
        if 1 <= marker <= len(chunks):
            chunk = chunks[marker - 1]
            citations.append(
                Citation(
                    marker=marker,
                    document_id=chunk.document_id,
                    document_title=chunk.document_title,
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                    snippet=chunk.content[:300],
                )
            )
    return citations


async def answer_query(query: str, user_id: str, db: AsyncSession) -> ResearchAnswer:
    candidates = await hybrid_search(query, db, user_id, top_k=DEFAULT_TOP_K)
    if not candidates:
        return ResearchAnswer(
            answer="I couldn't find any documents in your research library that address this question.",
            citations=[],
        )

    reranked = await rerank(query, candidates, top_n=DEFAULT_TOP_N)
    answer_text = await _synthesize(query, reranked)
    citations = _extract_citations(answer_text, reranked)
    return ResearchAnswer(answer=answer_text, citations=citations)
