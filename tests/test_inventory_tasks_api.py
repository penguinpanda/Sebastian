from __future__ import annotations

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_trigger_scan_expiring_task(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyAsyncResult:
        id = "celery-task-1"

    captured: dict[str, object] = {}

    def _fake_delay(days: int, trace_id: str | None = None):
        captured["days"] = days
        captured["trace_id"] = trace_id
        return DummyAsyncResult()

    monkeypatch.setattr("app.api.routes.inventory.scan_expiring_inventory.delay", _fake_delay)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/inventory/tasks/scan-expiring",
            params={"days": 3},
            headers={"x-trace-id": "trace-api-celery"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["task_id"] == "celery-task-1"
    assert payload["days"] == 3
    assert payload["trace_id"] == "trace-api-celery"
    assert captured["days"] == 3
    assert captured["trace_id"] == "trace-api-celery"
