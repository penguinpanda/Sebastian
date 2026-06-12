from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from app.api.routes.task_history import get_task_execution_log_service
from app.main import app


@pytest.mark.asyncio
async def test_get_task_history_by_task_id() -> None:
    class StubService:
        def get_by_task_id(self, task_id: str):
            if task_id != "celery-1":
                return None

            return type(
                "Log",
                (),
                {
                    "task_id": "celery-1",
                    "task_name": "app.tasks.inventory_tasks.scan_expiring_inventory",
                    "trace_id": "trace-1",
                    "status": "completed",
                    "input_payload": {"days": 3},
                    "output_payload": {"status": "ok"},
                    "error_detail": None,
                    "created_at": datetime.now(timezone.utc),
                    "started_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc),
                    "duration_ms": 12,
                },
            )()

    app.dependency_overrides[get_task_execution_log_service] = lambda: StubService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/tasks/history/celery-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "celery-1"
    assert payload["trace_id"] == "trace-1"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_task_history_by_trace_id() -> None:
    class StubService:
        def search(self, *, trace_id: str | None, status: str | None, limit: int):
            assert trace_id == "trace-1"
            assert status == "completed"
            assert limit == 5
            now = datetime.now(timezone.utc)
            return [
                type(
                    "Log",
                    (),
                    {
                        "task_id": "celery-1",
                        "task_name": "app.tasks.inventory_tasks.scan_expiring_inventory",
                        "trace_id": "trace-1",
                        "status": "completed",
                        "input_payload": {"days": 3},
                        "output_payload": {"status": "ok"},
                        "error_detail": None,
                        "created_at": now,
                        "started_at": now,
                        "finished_at": now,
                        "duration_ms": 12,
                    },
                )()
            ]

    app.dependency_overrides[get_task_execution_log_service] = lambda: StubService()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(
            "/api/tasks/history",
            params={"trace_id": "trace-1", "status": "completed", "limit": 5},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["task_id"] == "celery-1"
    app.dependency_overrides.clear()
