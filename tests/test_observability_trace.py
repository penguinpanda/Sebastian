from __future__ import annotations

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_trace_header_generated_when_missing() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.headers.get("x-trace-id")


@pytest.mark.asyncio
async def test_trace_header_preserved_when_provided() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health", headers={"x-trace-id": "trace-from-client"})

    assert response.status_code == 200
    assert response.headers.get("x-trace-id") == "trace-from-client"


@pytest.mark.asyncio
async def test_a2a_tasks_uses_trace_header() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/a2a/tasks",
            headers={"x-trace-id": "trace-from-client"},
            json={"message": "hello"},
        )

    assert response.status_code in (200, 503)
    assert response.headers.get("x-trace-id") == "trace-from-client"
