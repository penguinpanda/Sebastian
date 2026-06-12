from __future__ import annotations

import httpx
import pytest

from app.api.routes.mcp import get_mcp_adapter
from app.main import app
from app.schemas.mcp import MCPInvokeResponse


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
async def test_mcp_invoke_uses_request_trace_when_payload_trace_missing() -> None:
    class StubAdapter:
        def invoke(self, request):
            assert request.trace_id == "trace-from-header"
            return MCPInvokeResponse(
                trace_id=request.trace_id,
                tool_name=request.name,
                result={"ok": True},
                latency_ms=1,
                status="ok",
            )

    app.dependency_overrides[get_mcp_adapter] = lambda: StubAdapter()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/mcp/invoke",
            headers={"x-trace-id": "trace-from-header"},
            json={"name": "inventory.summary", "input": {"days": 7}},
        )

    assert response.status_code == 200
    assert response.json()["trace_id"] == "trace-from-header"
    assert response.headers.get("x-trace-id") == "trace-from-header"
    app.dependency_overrides.clear()
