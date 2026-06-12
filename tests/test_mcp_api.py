from __future__ import annotations

import httpx
import pytest

from app.api.routes.mcp import get_mcp_adapter
from app.main import app
from app.schemas.mcp import MCPInvokeResponse, MCPToolSpec, MCPToolsResponse
from app.services.mcp_adapter import MCPInvocationError


@pytest.mark.asyncio
async def test_mcp_list_tools() -> None:
    class StubAdapter:
        def list_tools(self):
            return [
                MCPToolSpec(
                    name="inventory.summary",
                    description="x",
                    input_schema={},
                    output_schema={},
                    timeout_ms=1000,
                    idempotency_key_required=False,
                )
            ]

    app.dependency_overrides[get_mcp_adapter] = lambda: StubAdapter()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/mcp/tools")

    assert response.status_code == 200
    payload = MCPToolsResponse.model_validate(response.json())
    assert payload.tools[0].name == "inventory.summary"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_invoke_success() -> None:
    class StubAdapter:
        def invoke(self, request):
            return MCPInvokeResponse(
                trace_id="t-1",
                tool_name=request.name,
                result={"ok": True},
                latency_ms=10,
                status="ok",
            )

    app.dependency_overrides[get_mcp_adapter] = lambda: StubAdapter()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/mcp/invoke", json={"name": "inventory.summary", "input": {"days": 7}})

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "inventory.summary"
    assert payload["result"]["ok"] is True
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_invoke_validation_error() -> None:
    class StubAdapter:
        def invoke(self, request):
            raise MCPInvocationError("VALIDATION_ERROR", "bad input")

    app.dependency_overrides[get_mcp_adapter] = lambda: StubAdapter()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/mcp/invoke", json={"name": "inventory.summary", "input": {"days": 999}})

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"] == "VALIDATION_ERROR"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_list_tools_includes_p25_domains() -> None:
    class StubAdapter:
        def list_tools(self):
            return [
                MCPToolSpec(name="recipe.recommend", description="x"),
                MCPToolSpec(name="health.analyze", description="x"),
                MCPToolSpec(name="equipment.check", description="x"),
                MCPToolSpec(name="search.answer", description="x"),
            ]

    app.dependency_overrides[get_mcp_adapter] = lambda: StubAdapter()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/mcp/tools")

    assert response.status_code == 200
    names = {item["name"] for item in response.json()["tools"]}
    assert {"recipe.recommend", "health.analyze", "equipment.check", "search.answer"}.issubset(names)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_invoke_accepts_user_action_fields() -> None:
    class StubAdapter:
        def invoke(self, request):
            assert request.user_id == "u-1"
            assert request.action == "invoke"
            return MCPInvokeResponse(
                trace_id="t-2",
                tool_name=request.name,
                result={"ok": True, "_audit": {"user_id": request.user_id, "action": request.action}},
                latency_ms=8,
                status="ok",
            )

    app.dependency_overrides[get_mcp_adapter] = lambda: StubAdapter()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/mcp/invoke",
            json={"name": "recipe.recommend", "input": {"user_id": "u-1"}, "user_id": "u-1", "action": "invoke"},
        )

    assert response.status_code == 200
    assert response.json()["result"]["_audit"]["user_id"] == "u-1"
    app.dependency_overrides.clear()
