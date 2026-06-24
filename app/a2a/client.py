"""内部 A2A 客户端 — Agent 间进程内 A2A 通信。

Router Agent 通过此客户端将任务分发给子 Agent。
当前实现为进程内直接调用（可切换为 HTTP 以支持分布式）。

Usage:
    client = InternalA2AClient()
    task = await client.send_task(
        agent_name="recipe",
        message=Message.from_text("推荐一道低卡午餐"),
    )
    for artifact in task.artifacts:
        print(artifact.parts[0].text)
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.a2a.schemas import (
    Artifact,
    Message,
    SendTaskResponse,
    Task,
    TaskState,
)
from app.a2a.task_manager import TaskManager, get_task_manager

logger = logging.getLogger(__name__)


class AgentNotFoundError(Exception):
    """目标 Agent 未找到。"""
    def __init__(self, agent_name: str) -> None:
        super().__init__(f"Agent not found: {agent_name}")
        self.agent_name = agent_name


class InternalA2AClient:
    """Agent 间进程内 A2A 通信客户端。

    支持两种模式:
    1. blocking=True: 同步等待子 Agent 完成，返回 SendTaskResponse
    2. blocking=False: 立即返回 task，由调用方自行轮询/订阅
    """

    def __init__(self, task_manager: TaskManager | None = None) -> None:
        self._task_manager = task_manager or get_task_manager()
        self._agent_registry: dict[str, object] = {}  # agent_name → BaseAgent 实例

    # ── Agent 注册 ─────────────────────────────────────────────

    def register_agent(self, name: str, agent: object) -> None:
        """注册 Agent 实例到注册表。"""
        self._agent_registry[name] = agent
        logger.info("Agent registered: %s", name)

    def get_agent(self, name: str) -> object:
        """获取已注册的 Agent。"""
        if name not in self._agent_registry:
            raise AgentNotFoundError(name)
        return self._agent_registry[name]

    @property
    def registered_agents(self) -> list[str]:
        """列出已注册的 Agent 名称。"""
        return list(self._agent_registry.keys())

    # ── 任务发送 ───────────────────────────────────────────────

    async def send_task(
        self,
        agent_name: str,
        message: Message,
        *,
        context_id: str | None = None,
        blocking: bool = True,
        metadata: dict | None = None,
    ) -> SendTaskResponse:
        """向指定 Agent 发送 A2A 任务。

        Args:
            agent_name: 目标 Agent 名称（如 'recipe', 'health'）
            message: A2A 消息
            context_id: 会话上下文 ID
            blocking: 是否阻塞等待完成
            metadata: 附加元数据

        Returns:
            SendTaskResponse: 含 task 和可能的 direct_reply
        """
        agent = self.get_agent(agent_name)

        # 创建 A2A 任务
        task = self._task_manager.create_task(
            message=message,
            context_id=context_id,
            metadata=metadata or {},
        )

        logger.info(
            "Dispatching task %s → agent '%s' (blocking=%s)",
            task.id, agent_name, blocking,
        )

        # 调用 Agent 的 handle_task
        full_reply_parts: list[str] = []

        async for artifact in agent.handle_task(task, message):
            # 收集文本产出
            for part in artifact.parts:
                if hasattr(part, "text"):
                    full_reply_parts.append(part.text)

        direct_reply = "".join(full_reply_parts) if blocking else None

        return SendTaskResponse(
            task=task,
            direct_reply=direct_reply,
        )

    # ── 流式发送（SSE） ────────────────────────────────────────

    async def send_task_stream(
        self,
        agent_name: str,
        message: Message,
        *,
        context_id: str | None = None,
    ) -> AsyncIterator[Artifact]:
        """向 Agent 发送任务并以流式方式获取产出。

        适用于需要实时推送给前端的场景。
        """
        agent = self.get_agent(agent_name)

        task = self._task_manager.create_task(
            message=message,
            context_id=context_id,
        )

        async for artifact in agent.handle_task(task, message):
            yield artifact
