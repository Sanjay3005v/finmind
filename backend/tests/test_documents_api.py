"""API tests for /api/v1/documents.

Ingestion calls the real OpenAI embeddings endpoint via
`app.rag.embeddings.embed_texts` — mocked here (module-level monkeypatch on
`app.rag.ingestion.embed_texts`, the name `ingest_document` actually calls)
so the suite stays offline/deterministic and never spends real API credits.
Uses the same sqlite dependency-override `client` fixture as other API
tests (see conftest.py), which also provisions `documents` +
`document_chunks` tables.
"""
from __future__ import annotations

import io
import uuid

import pytest

from app.core.security import get_current_user_id
from app.main import app
from app.rag import ingestion


@pytest.fixture(autouse=True)
def _mock_embeddings(monkeypatch):
    async def _fake_embed_texts(texts):
        return [[0.001 * (i + 1)] * 1536 for i in range(len(texts))]

    monkeypatch.setattr(ingestion, "embed_texts", _fake_embed_texts)


def test_upload_text_document_ingests_and_returns_ready_status(client):
    file_content = b"This is a short research note about a diversified equity portfolio. " * 5
    resp = client.post(
        "/api/v1/documents",
        data={"title": "Test note", "source_type": "manual_upload"},
        files={"file": ("note.txt", io.BytesIO(file_content), "text/plain")},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ready"
    assert body["title"] == "Test note"
    assert body["source_type"] == "manual_upload"


def test_upload_document_with_unsupported_content_type_marks_failed_not_500(client):
    resp = client.post(
        "/api/v1/documents",
        data={"title": "Bad file", "source_type": "manual_upload"},
        files={"file": ("note.bin", io.BytesIO(b"\x00\x01\x02"), "application/octet-stream")},
    )
    assert resp.status_code == 201  # the upload itself succeeds; ingestion fails gracefully
    assert resp.json()["status"] == "failed"


def test_upload_document_rejects_invalid_source_type(client):
    resp = client.post(
        "/api/v1/documents",
        data={"title": "x", "source_type": "not_a_real_type"},
        files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 422


def test_list_documents_includes_own_upload(client):
    client.post(
        "/api/v1/documents",
        data={"title": "Mine", "source_type": "manual_upload"},
        files={"file": ("a.txt", io.BytesIO(b"hello world, this is a note"), "text/plain")},
    )
    resp = client.get("/api/v1/documents")
    assert resp.status_code == 200
    titles = [d["title"] for d in resp.json()]
    assert "Mine" in titles


def test_get_nonexistent_document_returns_404_standard_error_shape(client):
    resp = client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"


def test_document_owned_by_another_user_is_not_visible_for_delete(client):
    """Defense-in-depth / not-found-not-leaked check, same pattern as
    broker connections: a document owned by a different user must 404 on
    delete (never 403), and never leak whether the id exists."""
    create_resp = client.post(
        "/api/v1/documents",
        data={"title": "Other user's doc", "source_type": "manual_upload"},
        files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    doc_id = create_resp.json()["id"]

    other_override = app.dependency_overrides[get_current_user_id]

    async def _as_other_user():
        return str(uuid.uuid4())

    app.dependency_overrides[get_current_user_id] = _as_other_user
    try:
        delete_resp = client.delete(f"/api/v1/documents/{doc_id}")
        assert delete_resp.status_code == 404
        assert delete_resp.json()["error"]["code"] == "DOCUMENT_NOT_FOUND"
    finally:
        app.dependency_overrides[get_current_user_id] = other_override


def test_delete_own_document_removes_it(client):
    create_resp = client.post(
        "/api/v1/documents",
        data={"title": "To delete", "source_type": "manual_upload"},
        files={"file": ("a.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    doc_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_resp.status_code == 204

    get_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 404


def test_documents_require_authentication(client):
    original = app.dependency_overrides.pop(get_current_user_id)
    try:
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides[get_current_user_id] = original
