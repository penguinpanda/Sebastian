"""A2A SSE 流式推送 — Server-Sent Events 任务状态推送。

支持客户端通过 POST /a2a/tasks/{task_id}/subscribe 订阅任务状态变更。
底层通过 TaskManager 的 pub/sub 机制推送事件。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from sse_starlette.sse import EventSourceResponse

from app.a2a.schemas import (
    Artifact,
    TaskState,
    TaskStatus,
    TaskSubscriptionEvent,
)
from app.a2a.task_manager import TaskManager, get_task_manager

logger = logging.getLogger(__name__)


async def task_event_stream(
    task_id: str,
    task_manager: TaskManager | None = None,
    heartbeat_interval: float = 15.0,
) -> AsyncIterator[dict]:
    """SSE 事件生成器，向客户端推送任务状态变更。

    Args:
        task_id: 要订阅的任务 ID
        task_manager: TaskManager 实例
        heartbeat_interval: 心跳间隔（秒）

    Yields:
        SSE 格式的事件字典: {"event": "status_update", "data": "..."}
            或 {"event": "heartbeat", "data": ""}
    """
    mgr = task_manager or get_task_manager()

    # 检查任务是否存在
    try:
        task = mgr.get_task(task_id)
    except Exception:
        yield {
            "event": "error",
            "data": json.dumps({"error": f"Task not found: {task_id}"}),
        }
        return

    # 事件队列：用于跨协程传递状态变更
    queue: asyncio.Queue[TaskSubscriptionEvent] = asyncio.Queue()

    def on_status_change(tid: str, status: TaskStatus, artifact: Artifact | None = None):
        """TaskManager 回调：收到状态变更时塞入队列。"""
        is_final = status.state in (
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELED,
        )
        event = TaskSubscriptionEvent(
            task_id=tid,
            status=status,
            artifact=artifact,
            final=is_final,
        )
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("Event queue full for task %s, dropping event", tid)

    # 注册订阅
    mgr.subscribe(task_id, on_status_change)

    try:
        # 先推送当前状态
        yield {
            "event": "status_update",
            "data": TaskSubscriptionEvent(
                task_id=task_id,
                status=task.status,
                final=False,
            ).model_dump_json(),
        }

        # 持续推送
        while True:
            try:
                event: TaskSubscriptionEvent = await asyncio.wait_for(
                    queue.get(), timeout=heartbeat_interval
                )

                yield {
                    "event": "status_update",
                    "data": event.model_dump_json(),
                }

                if event.final:
                    logger.info("Task %s reached final state: %s", task_id, event.status.state.value)
                    break

            except asyncio.TimeoutError:
                # 发送心跳保持连接
                yield {"event": "heartbeat", "data": ""}

    except asyncio.CancelledError:
        logger.debug("SSE stream cancelled for task %s", task_id)
    finally:
        mgr.unsubscribe(task_id, on_status_change)
        logger.debug("SSE stream ended for task %s", task_id)


def build_sse_response(task_id: str, task_manager: TaskManager | None = None) -> EventSourceResponse:
    """构建 FastAPI SSE 响应，用于路由返回。

    Usage:
        @router.post("/tasks/{task_id}/subscribe")
        async def subscribe(task_id: str):
            return build_sse_response(task_id)
    """
    return EventSourceResponse(task_event_stream(task_id, task_manager))
