from __future__ import annotations

import json

import httpx
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_access_log_contains_required_structured_fields(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level("INFO", logger="app.access")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/health", headers={"x-trace-id": "trace-log-1"})

    assert response.status_code == 200
    access_records = [record for record in caplog.records if record.name == "app.access"]
    assert access_records, "expected structured access log records"

    payload = json.loads(access_records[-1].message)
    for key in ["trace_id", "user_id", "action", "route", "latency_ms"]:
        assert key in payload

    assert payload["trace_id"] == "trace-log-1"
    assert payload["route"] == "/api/health"
    assert payload["action"] == "get"
    assert isinstance(payload["latency_ms"], int)
