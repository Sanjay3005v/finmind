"""Hybrid retrieval: pgvector cosine similarity + Postgres full-text search
(`tsv @@ plainto_tsquery`), merged via reciprocal rank fusion
(`app/rag/fusion.py`).

This is the ONLY retrieval algorithm in the pipeline — real, deterministic
arithmetic over two real SQL queries. No LLM is involved anywhere in this
module (see `app/rag/rerank.py` for the one place an LLM is allowed to
touch ranking, and only by re-scoring what this module already retrieved).

Visibility: this runs through the app's privileged (service-role) DB
connection, which bypasses Postgres RLS, so the `documents`/`document_chunks`
RLS policies in docs/DATABASE_SCHEMA.sql are re-implemented explicitly here
in SQL — a document is visible if `user_id = :user_id` (owned) or
`user_id is null` (shared/global corpus).
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.rag.embeddings import embed_texts
from app.rag.fusion import DEFAULT_RANK_CONSTANT, reciprocal_rank_fusion

DEFAULT_TOP_K = 10
# Fetch more candidates from each individual ranked list than the final
# top_k so RRF has enough signal to merge before truncating to top_k.
CANDIDATE_MULTIPLIER = 3


@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    score: float


_VECTOR_SEARCH_SQL = text(
    """
    select c.id, c.document_id, d.title, c.chunk_index, c.content
    from document_chunks c
    join documents d on d.id = c.document_id
    where (d.user_id = :user_id or d.user_id is null)
      and c.embedding is not null
    order by c.embedding <=> cast(:query_vec as vector)
    limit :limit
    """
)

_FTS_SEARCH_SQL = text(
    """
    select c.id, c.document_id, d.title, c.chunk_index, c.content
    from document_chunks c
    join documents d on d.id = c.document_id
    where (d.user_id = :user_id or d.user_id is null)
      and c.tsv @@ plainto_tsquery('english', :q)
    order by ts_rank(c.tsv, plainto_tsquery('english', :q)) desc
    limit :limit
    """
)


def _vector_literal(vector: list[float]) -> str:
    """Renders a Python float list as pgvector's text input format, e.g.
    `[0.1,0.2,0.3]`, for the `cast(:query_vec as vector)` parameter."""
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


async def hybrid_search(
    query: str, db: AsyncSession, user_id: str, top_k: int = DEFAULT_TOP_K
) -> list[RetrievedChunk]:
    """Embeds `query`, runs vector similarity and full-text search scoped to
    documents visible to `user_id`, fuses the two rankings with reciprocal
    rank fusion, and returns the top `top_k` merged candidates with their
    source document metadata. Only ever returns chunks that one of the two
    real search queries actually retrieved."""
    if not query or not query.strip():
        return []

    owner_uuid = UUID(user_id)
    fetch_limit = max(top_k * CANDIDATE_MULTIPLIER, top_k)

    vectors = await embed_texts([query])
    query_vector = vectors[0]

    vector_rows = (
        await db.execute(
            _VECTOR_SEARCH_SQL,
            {"user_id": owner_uuid, "query_vec": _vector_literal(query_vector), "limit": fetch_limit},
        )
    ).all()

    fts_rows = (
        await db.execute(_FTS_SEARCH_SQL, {"user_id": owner_uuid, "q": query, "limit": fetch_limit})
    ).all()

    row_by_id: dict[str, object] = {}
    vector_ids: list[str] = []
    for row in vector_rows:
        chunk_id = str(row[0])
        vector_ids.append(chunk_id)
        row_by_id[chunk_id] = row

    fts_ids: list[str] = []
    for row in fts_rows:
        chunk_id = str(row[0])
        fts_ids.append(chunk_id)
        row_by_id.setdefault(chunk_id, row)

    fused = reciprocal_rank_fusion([vector_ids, fts_ids], k=DEFAULT_RANK_CONSTANT)

    results: list[RetrievedChunk] = []
    for chunk_id, score in fused[:top_k]:
        row = row_by_id[chunk_id]
        results.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                document_id=str(row[1]),
                document_title=row[2],
                chunk_index=row[3],
                content=row[4],
                score=score,
            )
        )
    return results
