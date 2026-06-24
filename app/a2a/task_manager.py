"""A2A 任务管理器 — 管理任务生命周期。

底层存储: PostgreSQL（持久化）+ Redis（实时状态缓存）。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.a2a.schemas import (
    Artifact,
    Message,
    Task,
    TaskState,
    TaskStatus,
)

logger = logging.getLogger(__name__)


class TaskNotFoundError(Exception):
    """任务不存在错误。"""
    def __init__(self, task_id: str) -> None:
        super().__init__(f"Task not found: {task_id}")
        self.task_id = task_id


class TaskManager:
    """A2A 任务生命周期管理器。

    任务状态流转:
      SUBMITTED → WORKING → COMPLETED
                   ↓         ↓
              INPUT_REQUIRED  FAILED
                   ↓
               CANCELED
    """

    def __init__(self) -> None:
        # 内存存储（后续可替换为 PG + Redis 双写）
        self._tasks: dict[str, Task] = {}
        # 状态订阅者：task_id → [callback]
        self._subscribers: dict[str, list[callable]] = {}

    # ── 任务 CRUD ───────────────────────────────────────────────

    def create_task(
        self,
        message: Message,
        *,
        context_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Task:
        """创建一个新的 A2A 任务。"""
        task = Task(
            id=str(uuid4()),
            context_id=context_id,
            status=TaskStatus(state=TaskState.SUBMITTED),
            history=[message],
            metadata=metadata or {},
        )
        self._tasks[task.id] = task
        logger.info("Task created: id=%s context=%s", task.id, context_id)
        return task

    def get_task(self, task_id: str) -> Task:
        """获取任务详情。"""
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id)
        return self._tasks[task_id]

    def cancel_task(self, task_id: str) -> bool:
        """取消任务。"""
        task = self.get_task(task_id)
        if task.status.state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED):
            return False  # 终态不可取消

        self._update_status(task_id, TaskState.CANCELED, "Task canceled by user")
        return True

    # ── 状态管理 ────────────────────────────────────────────────

    def update_status(
        self,
        task_id: str,
        state: TaskState,
        message: str = "",
    ) -> TaskStatus:
        """更新任务状态。"""
        return self._update_status(task_id, state, message)

    def set_working(self, task_id: str, message: str = "Agent is processing...") -> TaskStatus:
        """标记任务为工作中。"""
        return self._update_status(task_id, TaskState.WORKING, message)

    def set_completed(self, task_id: str, message: str = "Task completed") -> TaskStatus:
        """标记任务为已完成。"""
        return self._update_status(task_id, TaskState.COMPLETED, message)

    def set_failed(self, task_id: str, message: str = "Task failed") -> TaskStatus:
        """标记任务为失败。"""
        return self._update_status(task_id, TaskState.FAILED, message)

    def _update_status(self, task_id: str, state: TaskState, message: str) -> TaskStatus:
        """内部状态更新 + 通知订阅者。"""
        task = self.get_task(task_id)
        new_status = TaskStatus(state=state, message=message)
        task.status = new_status
        task.updated_at = datetime.now(timezone.utc).isoformat()
        logger.debug("Task %s → %s: %s", task_id, state.value, message)

        # 通知 SSE 订阅者
        self._notify_subscribers(task_id, new_status)
        return new_status

    # ── 产出管理 ────────────────────────────────────────────────

    def add_artifact(self, task_id: str, artifact: Artifact) -> None:
        """为任务添加产出。"""
        task = self.get_task(task_id)
        artifact.index = len(task.artifacts)
        task.artifacts.append(artifact)
        task.updated_at = datetime.now(timezone.utc).isoformat()

        # 流式场景：推送增量产出
        self._notify_subscribers(task_id, task.status, artifact)

    def add_text_artifact(self, task_id: str, text: str, metadata: dict | None = None) -> Artifact:
        """便捷方法：添加纯文本产出。"""
        artifact = Artifact.from_text(text, metadata=metadata or {})
        self.add_artifact(task_id, artifact)
        return artifact

    # ── 消息历史 ────────────────────────────────────────────────

    def add_message(self, task_id: str, message: Message) -> None:
        """为任务追加一条消息。"""
        task = self.get_task(task_id)
        task.history.append(message)
        task.updated_at = datetime.now(timezone.utc).isoformat()

    # ── 订阅/通知（SSE 支持）───────────────────────────────────

    def subscribe(self, task_id: str, callback: callable) -> None:
        """注册任务状态变更回调。"""
        if task_id not in self._subscribers:
            self._subscribers[task_id] = []
        self._subscribers[task_id].append(callback)
        logger.debug("Subscriber added for task %s (total: %d)", task_id, len(self._subscribers[task_id]))

    def unsubscribe(self, task_id: str, callback: callable) -> None:
        """取消注册回调。"""
        if task_id in self._subscribers:
            self._subscribers[task_id] = [
                cb for cb in self._subscribers[task_id] if cb is not callback
            ]

    def _notify_subscribers(
        self,
        task_id: str,
        status: TaskStatus,
        artifact: Artifact | None = None,
    ) -> None:
        """向所有订阅者推送事件。"""
        if task_id not in self._subscribers:
            return

        for callback in self._subscribers[task_id]:
            try:
                callback(task_id, status, artifact)
            except Exception:
                logger.exception("Subscriber callback failed for task %s", task_id)

    # ── 查询 ────────────────────────────────────────────────────

    def task_exists(self, task_id: str) -> bool:
        """检查任务是否存在。"""
        return task_id in self._tasks

    def list_tasks(self, context_id: str | None = None) -> list[Task]:
        """列出任务（可按上下文过滤）。"""
        if context_id:
            return [t for t in self._tasks.values() if t.context_id == context_id]
        return list(self._tasks.values())

    def get_active_task_count(self) -> int:
        """获取活跃（未完成/未失败/未取消）任务数。"""
        terminal = (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED)
        return sum(1 for t in self._tasks.values() if t.status.state not in terminal)


# 全局单例
_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """获取全局 TaskManager 单例。"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
