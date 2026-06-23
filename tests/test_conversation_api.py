"""测试 Conversation 持久化 API。"""

import os
import tempfile

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.api.dependencies import get_db_session
from app.db.base import Base
from app.main import app
from app.models.conversation import Conversation


def _make_engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite+pysqlite:///{path}", connect_args={"check_same_thread": False})
    engine._test_db_path = path
    return engine


@pytest.fixture
def db_session():
    engine = _make_engine()
    Base.metadata.create_all(engine)
    db = Session(engine)
    yield db
    db.close()
    engine.dispose()
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_save_conversation_new(db_session) -> None:
    app.dependency_overrides[get_db_session] = lambda: db_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/api/conversations/save", json={
            "user_id": "u1",
            "date": "2026-06-12",
            "messages": [
                {"id": "1", "role": "user", "content": "你好"},
                {"id": "2", "role": "assistant", "content": "你好！"},
            ],
        })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "u1"
    assert len(data["messages"]) == 2

    # 验证 DB
    rows = db_session.scalars(
        select(Conversation).where(Conversation.user_id == "u1")
    ).all()
    assert len(rows) == 1

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_save_conversation_overwrite(db_session) -> None:
    """再次保存同一日期应覆盖消息。"""
    app.dependency_overrides[get_db_session] = lambda: db_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/conversations/save", json={
            "user_id": "u1", "date": "2026-06-12",
            "messages": [{"id": "1", "role": "user", "content": "第一版"}],
        })
        resp = await client.post("/api/conversations/save", json={
            "user_id": "u1", "date": "2026-06-12",
            "messages": [{"id": "2", "role": "user", "content": "第二版"}],
        })
    assert resp.status_code == 200
    assert len(resp.json()["messages"]) == 1
    assert resp.json()["messages"][0]["content"] == "第二版"

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_conversation_empty(engine) -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.get("/api/conversations", params={
            "user_id": "u1", "date": "2026-06-12",
        })
    assert resp.status_code == 200
    assert resp.json().get("messages") == []


@pytest.mark.asyncio
async def test_list_conversation_dates(db_session) -> None:
    app.dependency_overrides[get_db_session] = lambda: db_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        await client.post("/api/conversations/save", json={
            "user_id": "u1", "date": "2026-06-10", "messages": [],
        })
        await client.post("/api/conversations/save", json={
            "user_id": "u1", "date": "2026-06-12", "messages": [],
        })
        resp = await client.get("/api/conversations/dates", params={"user_id": "u1"})
    assert resp.status_code == 200
    dates = resp.json()["dates"]
    assert "2026-06-12" in dates
    assert "2026-06-10" in dates

    app.dependency_overrides.clear()
