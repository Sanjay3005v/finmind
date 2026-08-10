"""API tests for /api/v1/broker-connections.

Uses the `client` fixture from conftest.py, which overrides `get_db` (in-memory
SQLite) and `get_current_user_id` (fixed test user) — no real Supabase
Postgres connection or JWT verification happens in this file.
"""
import uuid

from app.core.security import get_current_user_id
from app.main import app


def test_create_broker_connection_defaults_to_paper_mode_and_connected_status(client):
    resp = client.post("/api/v1/broker-connections", json={"broker": "dhan"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["broker"] == "dhan"
    assert body["mode"] == "paper"
    assert body["status"] == "connected"
    assert "encrypted_credentials" not in body


def test_create_broker_connection_with_credentials_never_leaks_them(client):
    resp = client.post(
        "/api/v1/broker-connections",
        json={"broker": "angelone", "credentials": {"password": "super-secret-value"}},
    )

    assert resp.status_code == 201
    raw_text = resp.text
    assert "super-secret-value" not in raw_text
    assert "encrypted_credentials" not in raw_text


def test_create_broker_connection_rejects_unknown_broker(client):
    resp = client.post("/api/v1/broker-connections", json={"broker": "robinhood"})
    assert resp.status_code == 422


def test_list_broker_connections_only_returns_current_user(client):
    resp1 = client.post("/api/v1/broker-connections", json={"broker": "dhan"})
    resp2 = client.post("/api/v1/broker-connections", json={"broker": "upstox"})
    assert resp1.status_code == 201 and resp2.status_code == 201

    resp = client.get("/api/v1/broker-connections")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert {c["broker"] for c in body} == {"dhan", "upstox"}


def test_sync_paper_connection_upserts_mock_holdings(client):
    create_resp = client.post("/api/v1/broker-connections", json={"broker": "fyers"})
    connection_id = create_resp.json()["id"]

    sync_resp = client.post(f"/api/v1/broker-connections/{connection_id}/sync")

    assert sync_resp.status_code == 200
    body = sync_resp.json()
    assert body["connection_id"] == connection_id
    assert body["holdings_synced"] >= 4  # matches MockAdapter's fixture holdings
    assert body["last_synced_at"] is not None

    # Syncing again should upsert, not duplicate.
    sync_resp_2 = client.post(f"/api/v1/broker-connections/{connection_id}/sync")
    assert sync_resp_2.json()["holdings_synced"] == body["holdings_synced"]


def test_delete_broker_connection_removes_it(client):
    create_resp = client.post("/api/v1/broker-connections", json={"broker": "dhan"})
    connection_id = create_resp.json()["id"]

    delete_resp = client.delete(f"/api/v1/broker-connections/{connection_id}")
    assert delete_resp.status_code == 204

    list_resp = client.get("/api/v1/broker-connections")
    assert connection_id not in {c["id"] for c in list_resp.json()}


def test_delete_nonexistent_connection_returns_404_standard_error_shape(client):
    resp = client.delete(f"/api/v1/broker-connections/{uuid.uuid4()}")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "BROKER_CONNECTION_NOT_FOUND"


def test_broker_connection_owned_by_another_user_is_not_visible(client):
    """Defense-in-depth check: a connection that belongs to a different user
    must 404 (never leak existence), matching the `get_owned_portfolio`
    pattern. Creates the "other user's" connection by temporarily swapping
    the `get_current_user_id` override — avoids touching the DB directly so
    the test stays on the same TestClient/event-loop machinery throughout."""
    other_user_override = app.dependency_overrides[get_current_user_id]

    async def _as_other_user() -> str:
        return str(uuid.uuid4())

    app.dependency_overrides[get_current_user_id] = _as_other_user
    other_create_resp = client.post("/api/v1/broker-connections", json={"broker": "dhan"})
    other_connection_id = other_create_resp.json()["id"]

    # Restore the fixture's original (fixed test user) override.
    app.dependency_overrides[get_current_user_id] = other_user_override

    sync_resp = client.post(f"/api/v1/broker-connections/{other_connection_id}/sync")
    assert sync_resp.status_code == 404
    assert sync_resp.json()["error"]["code"] == "BROKER_CONNECTION_NOT_FOUND"

    delete_resp = client.delete(f"/api/v1/broker-connections/{other_connection_id}")
    assert delete_resp.status_code == 404


def test_broker_connections_require_authentication(client):
    # Temporarily drop the auth override to confirm the route is still
    # protected by the real dependency when not overridden.
    original = app.dependency_overrides.pop(get_current_user_id)
    try:
        resp = client.get("/api/v1/broker-connections")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides[get_current_user_id] = original
