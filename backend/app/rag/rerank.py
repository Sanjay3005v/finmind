"""LLM-as-judge reranking.

This is the ONLY place in the RAG pipeline an LLM is allowed to touch
retrieval ranking, and even here it may only re-score candidates that
`app/rag/retrieval.py::hybrid_search` already retrieved with a real,
deterministic algorithm — it can never introduce a new candidate, only
reorder/filter the list it was handed.

Reranking is an enhancement, not a hard dependency: if the API call fails
or returns something unparseable, we log a warning and fall back to the
first `top_n` candidates in their original hybrid_search order rather than
raising.
"""
from __future__ import annotations

import json
from typing import Sequence

import httpx
import structlog

from app.core.config import get_settings
from app.rag.retrieval import RetrievedChunk

logger = structlog.get_logger(__name__)

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
RERANK_MODEL = "gpt-4.1-mini"
DEFAULT_TOP_N = 5
_TIMEOUT_SECONDS = 30.0
_MAX_SNIPPET_CHARS = 1500

_SYSTEM_PROMPT = (
    "You are a relevance-scoring assistant for a financial research retrieval "
    "system. You will be given a user query and a numbered list of candidate "
    "text passages that a separate search system already retrieved. Score how "
    "relevant EACH candidate is to answering the query, from 0 (irrelevant) to "
    "10 (directly answers the query). Respond with strict JSON of the shape "
    '{"scores": [<score for candidate 0>, <score for candidate 1>, ...]}. '
    "The scores array must have exactly one number per candidate, in the same "
    "order they were given. Do not add, remove, merge, or reorder candidates "
    "yourself — only provide the scores array."
)


def _build_user_prompt(query: str, candidates: Sequence[RetrievedChunk]) -> str:
    lines = [f"Query: {query}", "", "Candidates:"]
    for idx, candidate in enumerate(candidates):
        snippet = candidate.content[:_MAX_SNIPPET_CHARS]
        lines.append(f"[{idx}] {snippet}")
    return "\n".join(lines)


async def rerank(
    query: str, candidates: list[RetrievedChunk], top_n: int = DEFAULT_TOP_N
) -> list[RetrievedChunk]:
    """Re-scores `candidates` via one OpenAI chat completion call and
    returns the top `top_n` by score. Falls back to the first `top_n`
    candidates in their original order (logging a warning) on any failure."""
    if not candidates:
        return []

    fallback = candidates[:top_n]

    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        logger.warning("rerank_skipped_no_api_key")
        return fallback

    payload = {
        "model": RERANK_MODEL,
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(query, candidates)},
        ],
    }
    headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(OPENAI_CHAT_URL, json=payload, headers=headers)
        if response.status_code != 200:
            raise ValueError(f"rerank API returned status {response.status_code}: {response.text[:300]}")

        body = response.json()
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        scores = parsed["scores"]
        if not isinstance(scores, list) or len(scores) != len(candidates):
            raise ValueError("scores array length does not match candidate count")

        scored = list(zip(candidates, (float(s) for s in scores)))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [candidate for candidate, _ in scored[:top_n]]
    except Exception as exc:  # noqa: BLE001 — any failure here must degrade gracefully, never raise
        logger.warning("rerank_failed_falling_back", error=str(exc))
        return fallback
