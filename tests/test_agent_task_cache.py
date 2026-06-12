from __future__ import annotations

from app.services.agent_task_cache import get_agent_task_status, set_agent_task_status


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}
        self.ex_by_key: dict[str, int | None] = {}

    def set(self, key: str, value: str, ex: int | None = None) -> bool:
        self._store[key] = value
        self.ex_by_key[key] = ex
        return True

    def get(self, key: str) -> str | None:
        return self._store.get(key)


def test_agent_task_status_cache_roundtrip(monkeypatch) -> None:
    fake = FakeRedis()

    monkeypatch.setattr("app.services.agent_task_cache.get_redis_client", lambda: fake)
    monkeypatch.setattr(
        "app.services.agent_task_cache.get_settings",
        lambda: type("S", (), {"agent_task_status_ttl_seconds": 123})(),
    )

    ok = set_agent_task_status(
        "task-1",
        "running",
        user_id="u-1",
        detail={"message": "hello"},
    )

    assert ok is True
    value = get_agent_task_status("task-1")
    assert value is not None
    assert value["task_id"] == "task-1"
    assert value["status"] == "running"
    assert value["user_id"] == "u-1"
    assert value["detail"] == {"message": "hello"}
    assert fake.ex_by_key["agent:task:task-1:status"] == 123


def test_agent_task_status_cache_fail_safe(monkeypatch) -> None:
    class BrokenRedis:
        def set(self, *args, **kwargs):
            raise RuntimeError("redis down")

        def get(self, *args, **kwargs):
            raise RuntimeError("redis down")

    monkeypatch.setattr("app.services.agent_task_cache.get_redis_client", lambda: BrokenRedis())

    assert set_agent_task_status("task-2", "failed", detail={"error": "x"}) is False
    assert get_agent_task_status("task-2") is None
