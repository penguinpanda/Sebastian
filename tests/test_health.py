import pytest
import httpx

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_dependencies_health_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.check_database_health",
        lambda: {"status": "ok", "detail": "select 1 ok"},
    )
    monkeypatch.setattr(
        "app.api.routes.health.check_redis_health",
        lambda: {"status": "ok", "detail": "pong"},
    )
    monkeypatch.setattr(
        "app.api.routes.health.check_elasticsearch_health",
        lambda: {"status": "error", "detail": "conn refused"},
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health/dependencies")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["postgres"]["status"] == "ok"
    assert payload["redis"]["status"] == "ok"
    assert payload["elasticsearch"]["status"] == "error"


@pytest.mark.asyncio
async def test_readiness_health_endpoint_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.check_database_health",
        lambda: {"status": "ok", "detail": "select 1 ok"},
    )
    monkeypatch.setattr(
        "app.api.routes.health.check_redis_health",
        lambda: {"status": "ok", "detail": "pong"},
    )
    monkeypatch.setattr(
        "app.api.routes.health.check_elasticsearch_health",
        lambda: {"status": "ok", "detail": "connected"},
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health/readiness")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness_health_endpoint_degraded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.api.routes.health.check_database_health",
        lambda: {"status": "ok", "detail": "select 1 ok"},
    )
    monkeypatch.setattr(
        "app.api.routes.health.check_redis_health",
        lambda: {"status": "ok", "detail": "pong"},
    )
    monkeypatch.setattr(
        "app.api.routes.health.check_elasticsearch_health",
        lambda: {"status": "error", "detail": "unavailable"},
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health/readiness")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
