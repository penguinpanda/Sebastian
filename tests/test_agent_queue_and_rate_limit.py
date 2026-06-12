from __future__ import annotations

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_agent_chat_rate_limit_exceeded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.agent.check_agent_rate_limit", lambda user_id: False)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/agent/chat", json={"message": "hello", "user_id": "u-limit"})

    assert response.status_code == 429
    assert response.json()["detail"] == "Rate limit exceeded"


@pytest.mark.asyncio
async def test_agent_queue_stats_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.routes.agent.get_agent_queue_size", lambda: 7)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/agent/queue/stats")

    assert response.status_code == 200
    assert response.json()["queue_size"] == 7
