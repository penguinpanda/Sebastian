from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.schemas.inventory import ExpiringInventoryItem
from app.tasks.inventory_tasks import scan_expiring_inventory


def test_scan_expiring_inventory_task(monkeypatch) -> None:
    class DummySession:
        def close(self):
            return None

    monkeypatch.setattr("app.tasks.inventory_tasks.get_session_factory", lambda: (lambda: DummySession()))

    class DummyRepo:
        def __init__(self, db):
            self.db = db

    monkeypatch.setattr("app.tasks.inventory_tasks.PostgresInventoryRepository", DummyRepo)

    class DummyService:
        def __init__(self, repository):
            self.repository = repository

        def expiring_items(self, days: int):
            return [
                ExpiringInventoryItem(
                    id=uuid4(),
                    item_type="ingredient",
                    name="Milk",
                    quantity=1,
                    unit="bottle",
                    expire_date=date(2026, 6, 12),
                    days_left=1,
                )
            ]

    monkeypatch.setattr("app.tasks.inventory_tasks.InventoryService", DummyService)

    queue_messages = []
    monkeypatch.setattr(
        "app.tasks.inventory_tasks.enqueue_agent_task",
        lambda task_id, user_id, message, trace_id=None: queue_messages.append((task_id, user_id, message, trace_id)) or True,
    )

    result = scan_expiring_inventory(days=3, trace_id="trace-celery-1")

    assert result["status"] == "ok"
    assert result["count"] == 1
    assert result["trace_id"] == "trace-celery-1"
    assert result["alerts"][0]["name"] == "Milk"
    assert len(queue_messages) == 1
    assert queue_messages[0][1] == "system"
    assert queue_messages[0][3] == "trace-celery-1"


def test_scan_expiring_inventory_task_failure_enqueues_notification(monkeypatch) -> None:
    class DummySession:
        def close(self):
            return None

    monkeypatch.setattr("app.tasks.inventory_tasks.get_session_factory", lambda: (lambda: DummySession()))

    class DummyRepo:
        def __init__(self, db):
            self.db = db

    monkeypatch.setattr("app.tasks.inventory_tasks.PostgresInventoryRepository", DummyRepo)

    class DummyService:
        def __init__(self, repository):
            self.repository = repository

        def expiring_items(self, days: int):
            raise RuntimeError("db failure")

    monkeypatch.setattr("app.tasks.inventory_tasks.InventoryService", DummyService)

    queue_messages = []
    monkeypatch.setattr(
        "app.tasks.inventory_tasks.enqueue_agent_task",
        lambda task_id, user_id, message, trace_id=None: queue_messages.append((task_id, user_id, message, trace_id)) or True,
    )

    with_exception = False
    try:
        scan_expiring_inventory(days=3, trace_id="trace-celery-fail")
    except Exception:
        with_exception = True

    assert with_exception is True

    assert len(queue_messages) == 1
    assert queue_messages[0][0] == "inventory-expiring-scan-failure"
    assert queue_messages[0][1] == "system"
    assert "inventory scan failed" in queue_messages[0][2]
    assert queue_messages[0][3] == "trace-celery-fail"
