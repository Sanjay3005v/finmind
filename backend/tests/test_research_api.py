"""API tests for POST /api/v1/research/query.

`hybrid_search` issues raw pgvector/tsvector SQL that only real Postgres
understands, so at this API layer we mock `research_service.hybrid_search`,
`research_service.rerank`, and `research_service._synthesize` directly
rather than hitting a real DB or spending real OpenAI credits — the citation
extraction/filtering logic in `research_service.answer_query` itself still
runs for real against these mocked inputs.
"""
from __future__ import annotations

import uuid

import pytest

from app.rag.retrieval import RetrievedChunk
from app.services import research_service

FAKE_CHUNKS = [
    RetrievedChunk(
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        document_title="Q3 Earnings Report",
        chunk_index=0,
        content="Revenue grew 12% year over year in Q3.",
        score=0.05,
    ),
    RetrievedChunk(
        chunk_id=str(uuid.uuid4()),
        document_id=str(uuid.uuid4()),
        document_title="Analyst Note",
        chunk_index=3,
        content="Margins compressed slightly due to input costs.",
        score=0.03,
    ),
]


@pytest.fixture(autouse=True)
def _mock_hybrid_search_and_rerank(monkeypatch):
    async def _fake_hybrid_search(query, db, user_id, top_k=10):
        return FAKE_CHUNKS

    async def _fake_rerank(query, candidates, top_n=5):
        return candidates  # identity — order/content already deterministic in tests

    monkeypatch.setattr(research_service, "hybrid_search", _fake_hybrid_search)
    monkeypatch.setattr(research_service, "rerank", _fake_rerank)


def test_research_query_returns_only_actually_cited_markers(client, monkeypatch):
    async def _fake_synthesize(query, chunks):
        return "Revenue grew strongly [1]. There is no data on competitor pricing in the sources."

    monkeypatch.setattr(research_service, "_synthesize", _fake_synthesize)

    resp = client.post("/api/v1/research/query", json={"query": "How did revenue perform?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"].startswith("Revenue grew strongly")
    assert len(body["citations"]) == 1
    assert body["citations"][0]["marker"] == 1
    assert body["citations"][0]["document_title"] == "Q3 Earnings Report"
    assert body["citations"][0]["chunk_id"] == FAKE_CHUNKS[0].chunk_id


def test_research_query_cites_multiple_sources(client, monkeypatch):
    async def _fake_synthesize(query, chunks):
        return "Revenue grew [1] while margins compressed [2]."

    monkeypatch.setattr(research_service, "_synthesize", _fake_synthesize)

    resp = client.post("/api/v1/research/query", json={"query": "Summarize performance"})
    body = resp.json()
    assert [c["marker"] for c in body["citations"]] == [1, 2]


def test_research_query_with_no_citations_in_answer_returns_empty_citations(client, monkeypatch):
    async def _fake_synthesize(query, chunks):
        return "I cannot determine this from the provided sources."

    monkeypatch.setattr(research_service, "_synthesize", _fake_synthesize)

    resp = client.post("/api/v1/research/query", json={"query": "What is the CEO's favorite color?"})
    assert resp.status_code == 200
    assert resp.json()["citations"] == []


def test_research_query_ignores_out_of_range_citation_markers():
    """Never fabricate a citation for a marker number the model hallucinated
    beyond the number of chunks it was actually given — unit-tested directly
    against the pure extraction function to pin down this hard rule."""
    citations = research_service._extract_citations("Some claim [1] and a bogus one [99].", FAKE_CHUNKS)
    assert [c.marker for c in citations] == [1]


def test_research_query_requires_authentication(client):
    from app.core.security import get_current_user_id
    from app.main import app

    original = app.dependency_overrides.pop(get_current_user_id)
    try:
        resp = client.post("/api/v1/research/query", json={"query": "test"})
        assert resp.status_code == 401
    finally:
        app.dependency_overrides[get_current_user_id] = original


def test_research_query_rejects_empty_query(client):
    resp = client.post("/api/v1/research/query", json={"query": ""})
    assert resp.status_code == 422


def test_research_query_with_no_retrieved_chunks_returns_graceful_answer(client, monkeypatch):
    async def _fake_empty_hybrid_search(query, db, user_id, top_k=10):
        return []

    monkeypatch.setattr(research_service, "hybrid_search", _fake_empty_hybrid_search)

    resp = client.post("/api/v1/research/query", json={"query": "anything"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["citations"] == []
    assert "couldn't find" in body["answer"].lower()
