from __future__ import annotations

from collections.abc import Generator
from uuid import UUID

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db_session
from app.main import app
from app.models.agent import AgentTask, ToolCallLog
from app.models.inventory import Inventory, InventoryTransaction
from app.db.base import Base


@pytest.fixture
def db_session_factory() -> Generator[sessionmaker[Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Ensure all models are registered in metadata before create_all.
    _ = (Inventory, InventoryTransaction, AgentTask, ToolCallLog)
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    try:
        yield SessionLocal
    finally:
        Base.metadata.drop_all(engine)


@pytest.mark.asyncio
async def test_agent_chat_persists_task_and_log(monkeypatch: pytest.MonkeyPatch, db_session_factory: sessionmaker[Session]) -> None:
    status_calls: list[tuple[str, str]] = []

    def override_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db

    monkeypatch.setattr("app.api.routes.agent.run_inventory_agent", lambda message, user_id=None: "Inventory looks good.")
    monkeypatch.setattr("app.api.routes.agent.check_agent_rate_limit", lambda user_id: True)
    monkeypatch.setattr("app.api.routes.agent.enqueue_agent_task", lambda task_id, user_id, message: True)
    monkeypatch.setattr(
        "app.api.routes.agent.set_agent_task_status",
        lambda task_id, status, **kwargs: status_calls.append((task_id, status)) or True,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/agent/chat", json={"message": "show summary", "user_id": "u-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Inventory looks good."
    assert body["task_id"]
    task_id = UUID(body["task_id"])
    assert status_calls[0] == (body["task_id"], "running")
    assert status_calls[1] == (body["task_id"], "completed")

    with db_session_factory() as db:
        task = db.scalar(select(AgentTask).where(AgentTask.id == task_id))
        assert task is not None
        assert task.status == "completed"
        assert task.output_payload == {"reply": "Inventory looks good."}

        logs = db.scalars(select(ToolCallLog).where(ToolCallLog.task_id == task.id)).all()
        assert len(logs) == 1
        assert logs[0].result_status == "ok"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_agent_chat_error_path_persists_failure(monkeypatch: pytest.MonkeyPatch, db_session_factory: sessionmaker[Session]) -> None:
    status_calls: list[tuple[str, str]] = []

    def override_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db

    def _raise(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr("app.api.routes.agent.run_inventory_agent", _raise)
    monkeypatch.setattr("app.api.routes.agent.check_agent_rate_limit", lambda user_id: True)
    monkeypatch.setattr("app.api.routes.agent.enqueue_agent_task", lambda task_id, user_id, message: True)
    monkeypatch.setattr(
        "app.api.routes.agent.set_agent_task_status",
        lambda task_id, status, **kwargs: status_calls.append((task_id, status)) or True,
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/agent/chat", json={"message": "show summary", "user_id": "u-2"})

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Something went wrong. Please try again."
    task_id = UUID(body["task_id"])
    assert status_calls[0] == (body["task_id"], "running")
    assert status_calls[1] == (body["task_id"], "failed")

    with db_session_factory() as db:
        task = db.scalar(select(AgentTask).where(AgentTask.id == task_id))
        assert task is not None
        assert task.status == "failed"
        assert "error" in task.output_payload

        logs = db.scalars(select(ToolCallLog).where(ToolCallLog.task_id == task.id)).all()
        assert len(logs) == 1
        assert logs[0].result_status == "error"
        assert "llm down" in (logs[0].error_detail or "")

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_task_status_prefers_cache(monkeypatch: pytest.MonkeyPatch, db_session_factory: sessionmaker[Session]) -> None:
    def override_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db

    monkeypatch.setattr(
        "app.api.routes.agent.get_agent_task_status",
        lambda task_id: {
            "status": "running",
            "user_id": "u-cache",
            "detail": {"message": "hello"},
        },
    )

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/agent/tasks/task-cache")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == "task-cache"
    assert payload["status"] == "running"
    assert payload["user_id"] == "u-cache"
    assert payload["detail"] == {"message": "hello"}
    assert payload["source"] == "cache"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_task_status_fallback_to_database(monkeypatch: pytest.MonkeyPatch, db_session_factory: sessionmaker[Session]) -> None:
    def override_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db
    monkeypatch.setattr("app.api.routes.agent.get_agent_task_status", lambda task_id: None)

    task_id = UUID("11111111-1111-1111-1111-111111111111")
    with db_session_factory() as db:
        db.add(
            AgentTask(
                id=task_id,
                user_id="u-db",
                task_type="inventory_chat",
                status="completed",
                input_payload={"message": "x"},
                output_payload={"reply": "ok"},
            )
        )
        db.commit()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/api/agent/tasks/{task_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == str(task_id)
    assert payload["status"] == "completed"
    assert payload["user_id"] == "u-db"
    assert payload["detail"] == {"reply": "ok"}
    assert payload["source"] == "database"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_task_status_not_found(monkeypatch: pytest.MonkeyPatch, db_session_factory: sessionmaker[Session]) -> None:
    def override_db() -> Generator[Session, None, None]:
        db = db_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db_session] = override_db
    monkeypatch.setattr("app.api.routes.agent.get_agent_task_status", lambda task_id: None)

    missing_task_id = "22222222-2222-2222-2222-222222222222"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/api/agent/tasks/{missing_task_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"

    app.dependency_overrides.clear()
