"""A2A BaseAgent — 所有 Agent 的抽象基类。

提供:
- 统一的 A2A handle_task 接口
- 上下文预算管理集成
- 对话历史注入
- 检索记忆注入
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator, ClassVar

from app.a2a.schemas import (
    AgentCard,
    Artifact,
    Message,
    Task,
    TaskState,
)
from app.a2a.task_manager import TaskManager, get_task_manager
from app.context.budget import ContextBudget
from app.context.history_manager import ConversationHistoryManager
from app.context.token_counter import TokenCounter, get_token_counter

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """A2A Agent 抽象基类。

    子类需要:
    1. 设置 agent_card 类变量
    2. 实现 handle_task() 异步生成器方法

    用法:
        class MyAgent(BaseAgent):
            agent_card = build_my_agent_card()

            async def handle_task(self, task, message):
                yield Artifact.from_text("处理中...")
                result = await self.do_work(message)
                yield Artifact.from_text(result)
    """

    agent_card: ClassVar[AgentCard]

    def __init__(
        self,
        task_manager: TaskManager | None = None,
        token_counter: TokenCounter | None = None,
        history_manager: ConversationHistoryManager | None = None,
    ) -> None:
        self._task_manager = task_manager or get_task_manager()
        self._token_counter = token_counter or get_token_counter()
        self._history_manager = history_manager or ConversationHistoryManager(
            token_counter=self._token_counter,
        )

    @property
    def task_manager(self) -> TaskManager:
        return self._task_manager

    @property
    def token_counter(self) -> TokenCounter:
        return self._token_counter

    @property
    def history_manager(self) -> ConversationHistoryManager:
        return self._history_manager

    # ── 主入口 ──────────────────────────────────────────────────

    async def handle_task(
        self,
        task: Task,
        message: Message,
        *,
        history: list[Message] | None = None,
        summary: str = "",
    ) -> AsyncIterator[Artifact]:
        """处理 A2A 任务的主入口。

        Args:
            task: A2A 任务对象
            message: 当前用户消息
            history: 对话历史（由调用方从 DB 加载）
            summary: 历史摘要（由调用方从 DB 缓存加载）

        Yields:
            Artifact: 任务产出（可多次 yield 实现流式）
        """
        # 更新任务状态
        self._task_manager.set_working(task.id)

        # 构建上下文预算
        budget = ContextBudget(token_counter=self._token_counter)

        # 构建 LLM prompt（子类实现具体逻辑）
        llm_messages = await self.build_prompt(
            message=message,
            history=history or [],
            summary=summary,
            budget=budget,
        )

        logger.debug(
            "Agent '%s' prompt built: %d messages, budget: %s",
            self.agent_card.name,
            len(llm_messages),
            budget.summary(),
        )

        # 调用子类的实际处理逻辑
        try:
            async for artifact in self.execute(task, message, llm_messages, budget):
                # 更新任务产出
                self._task_manager.add_artifact(task.id, artifact)
                yield artifact

            self._task_manager.set_completed(task.id)

        except Exception as exc:
            logger.exception("Agent '%s' task %s failed", self.agent_card.name, task.id)
            self._task_manager.set_failed(task.id, str(exc))
            yield Artifact.from_text(
                f"处理失败: {str(exc)}",
                metadata={"error": True},
            )

    # ── 子类需要实现的方法 ──────────────────────────────────────

    @abstractmethod
    async def execute(
        self,
        task: Task,
        message: Message,
        llm_messages: list[dict[str, str]],
        budget: ContextBudget,
    ) -> AsyncIterator[Artifact]:
        """子类实现：执行具体的 Agent 逻辑。

        Args:
            task: A2A 任务对象
            message: 当前用户消息
            llm_messages: 已构建好的 LLM prompt（已含 system/历史/检索）
            budget: 上下文预算（可供运行时查询）

        Yields:
            Artifact: 任务产出
        """
        ...

    async def build_prompt(
        self,
        message: Message,
        history: list[Message],
        summary: str,
        budget: ContextBudget,
    ) -> list[dict[str, str]]:
        """构建 LLM prompt（含 system、历史、检索记忆、当前消息）。

        子类可以覆盖此方法以自定义 prompt 构建逻辑。
        """
        messages: list[dict[str, str]] = []

        # 1. System Prompt
        system_text = self.get_system_prompt()
        system_tokens = budget.count(system_text)
        budget.allocate("system", system_tokens, system_text)
        messages.append({"role": "system", "content": system_text})

        # 2. 检索记忆（由子类覆盖 get_retrieved_context）
        retrieved = await self.get_retrieved_context(message, budget)
        if retrieved:
            retrieved_tokens = budget.count(retrieved)
            budget.allocate("retrieval", retrieved_tokens, retrieved)
            # 作为 system 补充注入
            messages.append({
                "role": "system",
                "content": f"[相关记忆]\n{retrieved}",
            })

        # 3. 对话历史
        history_msgs = self._history_manager.build_context_messages(
            history, budget, summary=summary,
        )
        messages.extend(history_msgs)

        # 4. 当前用户消息
        user_text = message.text
        user_tokens = budget.count(user_text)
        budget.allocate("current_message", user_tokens, user_text)
        messages.append({"role": "user", "content": user_text})

        return messages

    # ── 可覆盖的辅助方法 ────────────────────────────────────────

    def get_system_prompt(self) -> str:
        """获取 System Prompt。子类可覆盖。"""
        return f"你是 {self.agent_card.name}，{self.agent_card.description}。用中文回复，简洁专业。"

    async def get_retrieved_context(
        self,
        message: Message,
        budget: ContextBudget,
    ) -> str:
        """获取检索到的记忆上下文。子类可覆盖以集成 ES 检索。"""
        return ""

    # ── 工具方法 ────────────────────────────────────────────────

    def _extract_skill_params(self, message: Message) -> dict:
        """从 Message 的 DataPart 中提取技能参数。"""
        for part in message.parts:
            if hasattr(part, "data") and part.data:
                return part.data
        return {}
