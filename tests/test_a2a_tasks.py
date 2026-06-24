"""A2A Task API 测试 — 验证 /api/a2a/tasks 端点。"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.a2a.schemas import Message, SendTaskRequest, SendTaskResponse
from app.a2a.task_manager import TaskManager, get_task_manager
from app.main import app


# ── Task 创建测试 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a2a_create_task_returns_200() -> None:
    """POST /api/a2a/tasks 创建任务并返回 SendTaskResponse。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/a2a/tasks",
            json={"message": "hello", "user_id": "test-user"},
        )
    assert response.status_code in (200, 503)
    body = response.json()
    assert "task" in body
    assert "id" in body["task"]


@pytest.mark.asyncio
async def test_a2a_create_task_with_skill() -> None:
    """POST /api/a2a/tasks 带 skill_id 路由到对应 Agent。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/a2a/tasks",
            json={
                "message": "查看库存",
                "user_id": "test-user",
                "skill_id": "inventory.query",
            },
        )
    assert response.status_code in (200, 503)


@pytest.mark.asyncio
@pytest.mark.parametrize("skill_id,agent_name", [
    ("recipe.recommend", "recipe"),
    ("health.analyze", "health"),
    ("search.answer", "search"),
    ("equipment.check", "equipment"),
    ("inventory.summary", "inventory"),
    ("inventory.query", "inventory"),
    ("inventory.expiring", "inventory"),
])
async def test_all_skills_routing(skill_id: str, agent_name: str) -> None:
    """所有已注册的 skill_id 应能正确路由到对应 Agent。"""
    from app.a2a.server import _resolve_agent_from_skill
    result = _resolve_agent_from_skill(skill_id)
    assert result == agent_name


@pytest.mark.asyncio
async def test_a2a_create_task_with_context_id() -> None:
    """POST /api/a2a/tasks 支持 context_id。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/a2a/tasks",
            json={
                "message": "hello",
                "user_id": "test-user",
                "context_id": "session-123",
            },
        )
    assert response.status_code in (200, 503)


@pytest.mark.asyncio
async def test_a2a_standard_send_task_request_format() -> None:
    """A2A 标准 SendTaskRequest 格式也应被接受。"""
    transport = httpx.ASGITransport(app=app)
    # 构建标准 A2A Message
    msg = Message.from_text("hello standard format")
    request_body = SendTaskRequest(
        message=msg,
        blocking=True,
    ).model_dump()

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/a2a/tasks", json=request_body)
    assert response.status_code in (200, 503)


# ── Task 查询测试 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a2a_get_task_not_found() -> None:
    """GET /api/a2a/tasks/{id} 对不存在的任务返回 404。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/a2a/tasks/nonexistent-id")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_a2a_get_existing_task() -> None:
    """创建任务后能通过 GET 查询。"""
    tm = get_task_manager()
    task = tm.create_task(Message.from_text("test"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/api/a2a/tasks/{task.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == task.id


@pytest.mark.asyncio
async def test_a2a_cancel_task() -> None:
    """POST /api/a2a/tasks/{id}/cancel 取消任务。"""
    tm = get_task_manager()
    task = tm.create_task(Message.from_text("test"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(f"/api/a2a/tasks/{task.id}/cancel")
    assert response.status_code == 200
    assert response.json()["canceled"] is True


# ── Agent Card 端点测试 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_a2a_agent_card_recipe() -> None:
    """GET /api/a2a/agents/recipe/card 返回 Recipe Agent Card。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/a2a/agents/recipe/card")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Recipe Agent"
    assert len(body["skills"]) == 2


@pytest.mark.asyncio
async def test_a2a_well_known_agent() -> None:
    """GET /.well-known/agent.json 返回全局 Agent Card。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/.well-known/agent.json")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Sebastian"


# ── SSE 流式测试 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a2a_subscribe_nonexistent_task() -> None:
    """订阅不存在的任务返回 404。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/a2a/tasks/nonexistent/subscribe")
    assert response.status_code == 404


# ── 边缘情况测试 ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a2a_unknown_skill_returns_400() -> None:
    """未知 skill_id 返回 400。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/a2a/tasks",
            json={"message": "test", "skill_id": "unknown.skill"},
        )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_a2a_empty_message() -> None:
    """空消息应能正常处理。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/a2a/tasks",
            json={"message": "", "user_id": "test-user"},
        )
    assert response.status_code in (200, 503, 422)  # 空消息可能被拒绝


# ── TaskManager 单元测试 ───────────────────────────────────────

class TestTaskManagerUnit:
    """TaskManager 纯单元测试（不经过 HTTP）。"""

    def test_task_state_transitions(self) -> None:
        """任务状态流转: submitted → working → completed。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("hello"))
        assert task.status.state == "submitted"

        tm.set_working(task.id)
        assert tm.get_task(task.id).status.state == "working"

        tm.set_completed(task.id)
        assert tm.get_task(task.id).status.state == "completed"

    def test_task_failed_state(self) -> None:
        """任务可标记为失败。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("hello"))
        tm.set_failed(task.id, "Something went wrong")
        assert tm.get_task(task.id).status.state == "failed"
        assert tm.get_task(task.id).status.message == "Something went wrong"

    def test_multiple_artifacts_streaming(self) -> None:
        """多次添加产出支持流式场景。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("generate report"))
        tm.add_text_artifact(task.id, "Step 1: analyzing...")
        tm.add_text_artifact(task.id, "Step 2: generating...")
        tm.add_text_artifact(task.id, "Final result")

        retrieved = tm.get_task(task.id)
        assert len(retrieved.artifacts) == 3
        assert retrieved.artifacts[0].index == 0
        assert retrieved.artifacts[2].index == 2

    def test_task_history_messages(self) -> None:
        """任务历史记录所有消息。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("Q1"))
        tm.add_message(task.id, Message.from_text("A1", role="agent"))
        tm.add_message(task.id, Message.from_text("Q2"))

        retrieved = tm.get_task(task.id)
        assert len(retrieved.history) == 3

    def test_cannot_cancel_completed_task(self) -> None:
        """终态任务不可取消。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("hello"))
        tm.set_completed(task.id)
        assert not tm.cancel_task(task.id)

    def test_cannot_cancel_failed_task(self) -> None:
        """失败任务不可取消。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("hello"))
        tm.set_failed(task.id)
        assert not tm.cancel_task(task.id)
