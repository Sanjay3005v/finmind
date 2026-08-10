"""Health endpoint tests. No real Supabase/Redis connection required —
`/health/ready`'s DB and Redis checks are monkeypatched at the module level."""
import app.api.v1.health as health_module
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


async def _ok() -> bool:
    return True


async def _fail() -> bool:
    return False


def test_health_is_always_ok():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_when_db_and_redis_ok(monkeypatch):
    monkeypatch.setattr(health_module, "db_check", _ok)
    monkeypatch.setattr(health_module, "redis_check", _ok)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"database": "ok", "redis": "ok"}


def test_health_ready_returns_503_when_db_fails(monkeypatch):
    monkeypatch.setattr(health_module, "db_check", _fail)
    monkeypatch.setattr(health_module, "redis_check", _ok)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "failed"
    assert body["checks"]["redis"] == "ok"


def test_health_ready_returns_503_when_redis_fails(monkeypatch):
    monkeypatch.setattr(health_module, "db_check", _ok)
    monkeypatch.setattr(health_module, "redis_check", _fail)

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["redis"] == "failed"


def test_unknown_route_returns_standard_error_shape():
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert set(body["error"].keys()) == {"code", "message", "request_id"}


def test_protected_route_without_token_returns_401_standard_shape():
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"
