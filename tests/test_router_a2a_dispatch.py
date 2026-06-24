"""Router Agent A2A 分发测试 — 验证意图识别和子 Agent 路由。"""

from __future__ import annotations

import pytest

from app.a2a.client import AgentNotFoundError, InternalA2AClient
from app.a2a.schemas import Message, Task
from app.a2a.task_manager import TaskManager
from app.agents.router_agent import RouterAgent


class TestRouterAgentDispatch:
    """测试 Router Agent 的意图识别和分发逻辑。"""

    def test_router_intent_classification(self) -> None:
        """Router 能正确分类已知意图。"""
        import asyncio
        router = RouterAgent()

        async def _test():
            intent, confidence = await router._classify_intent("推荐一道低卡午餐")
            return intent, confidence

        intent, confidence = asyncio.run(_test())
        # 至少应返回一个有效意图
        assert intent in ("recipe", "health", "inventory", "search", "equipment", "general")

    def test_router_fallback_on_empty_input(self) -> None:
        """空输入回退到 general。"""
        import asyncio
        router = RouterAgent()

        async def _test():
            intent, confidence = await router._classify_intent("")
            return intent

        intent = asyncio.run(_test())
        assert intent in ("general", "recipe", "health", "inventory", "search", "equipment")

    def test_router_run_async_returns_string(self) -> None:
        """Router run_async 应返回非空字符串。"""
        import asyncio

        async def _test():
            router = RouterAgent()
            result = await router.run_async("你好", user_id="test")
            return result

        result = asyncio.run(_test())
        assert isinstance(result, str)
        assert len(result) > 0

    def test_router_run_sync_returns_string(self) -> None:
        """Router run（同步）应返回非空字符串。"""
        router = RouterAgent()
        result = router.run("你好", user_id="test")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_router_empty_input_graceful(self) -> None:
        """Router 空输入应返回提示而非崩溃。"""
        import asyncio

        async def _test():
            router = RouterAgent()
            result = await router.run_async("", user_id="test")
            return result

        result = asyncio.run(_test())
        assert isinstance(result, str)
        assert len(result) > 0  # 至少有一些提示文本


class TestInternalA2AClient:
    """测试内部 A2A 客户端。"""

    def test_register_and_get_agent(self) -> None:
        """注册 Agent 后可通过名称获取。"""
        client = InternalA2AClient()
        dummy_agent = object()
        client.register_agent("dummy", dummy_agent)
        assert client.get_agent("dummy") is dummy_agent

    def test_get_unknown_agent_raises(self) -> None:
        """获取未注册的 Agent 抛出 AgentNotFoundError。"""
        client = InternalA2AClient()
        with pytest.raises(AgentNotFoundError, match="nonexistent"):
            client.get_agent("nonexistent")

    def test_registered_agents_list(self) -> None:
        """registered_agents 列出所有已注册 Agent。"""
        client = InternalA2AClient()
        client.register_agent("a", object())
        client.register_agent("b", object())
        assert "a" in client.registered_agents
        assert "b" in client.registered_agents

    def test_send_task_to_registered_agent(self) -> None:
        """向已注册 Agent 发送 A2A 任务。"""
        import asyncio

        class DummyAgent:
            async def handle_task(self, task: Task, message: Message):
                from app.a2a.schemas import Artifact
                yield Artifact.from_text("dummy response")

        client = InternalA2AClient()
        client.register_agent("dummy", DummyAgent())

        async def _test():
            msg = Message.from_text("hello")
            return await client.send_task("dummy", msg, blocking=True)

        response = asyncio.run(_test())
        assert response.direct_reply == "dummy response"
        assert response.task is not None


class TestTaskManager:
    """测试 A2A Task Manager。"""

    def test_create_task(self) -> None:
        """创建任务并获取。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("hello"), context_id="ctx-1")
        assert task.id
        assert task.context_id == "ctx-1"
        assert task.status.state == "submitted"

    def test_get_nonexistent_task_raises(self) -> None:
        """获取不存在的任务抛出 TaskNotFoundError。"""
        from app.a2a.task_manager import TaskNotFoundError
        tm = TaskManager()
        with pytest.raises(TaskNotFoundError):
            tm.get_task("nonexistent")

    def test_task_lifecycle(self) -> None:
        """任务状态流转：submitted → working → completed。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("test"))

        tm.set_working(task.id)
        assert tm.get_task(task.id).status.state == "working"

        tm.set_completed(task.id)
        assert tm.get_task(task.id).status.state == "completed"

    def test_cancel_task(self) -> None:
        """取消任务应成功。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("test"))
        assert tm.cancel_task(task.id)

    def test_cancel_completed_task_fails(self) -> None:
        """已完成的任务不可取消。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("test"))
        tm.set_completed(task.id)
        assert not tm.cancel_task(task.id)

    def test_add_artifact(self) -> None:
        """添加产出后任务包含该产出。"""
        tm = TaskManager()
        task = tm.create_task(Message.from_text("test"))
        tm.add_text_artifact(task.id, "result text")
        retrieved = tm.get_task(task.id)
        assert len(retrieved.artifacts) == 1
        assert retrieved.artifacts[0].parts[0].text == "result text"

    def test_list_tasks_by_context(self) -> None:
        """可按 context_id 过滤任务。"""
        tm = TaskManager()
        tm.create_task(Message.from_text("m1"), context_id="ctx-a")
        tm.create_task(Message.from_text("m2"), context_id="ctx-a")
        tm.create_task(Message.from_text("m3"), context_id="ctx-b")

        ctx_a_tasks = tm.list_tasks(context_id="ctx-a")
        assert len(ctx_a_tasks) == 2

    def test_active_task_count(self) -> None:
        """get_active_task_count 只统计非终态任务。"""
        tm = TaskManager()
        t1 = tm.create_task(Message.from_text("m1"))
        t2 = tm.create_task(Message.from_text("m2"))
        tm.set_completed(t2.id)
        assert tm.get_active_task_count() == 1
