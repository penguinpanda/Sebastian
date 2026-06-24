"""A2A (Agent-to-Agent) 协议核心模块。

基于 Google A2A 规范 v0.3.0:
https://a2a-protocol.org/
"""

from .schemas import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Artifact,
    FilePart,
    Message,
    Part,
    SendTaskRequest,
    SendTaskResponse,
    Task,
    TaskState,
    TaskStatus,
    TaskSubscriptionEvent,
    TextPart,
)
from .task_manager import TaskManager
from .agent_card import build_global_agent_card, build_agent_card
from .streaming import task_event_stream

__all__ = [
    "AgentCapabilities",
    "AgentCard",
    "AgentSkill",
    "Artifact",
    "FilePart",
    "Message",
    "Part",
    "SendTaskRequest",
    "SendTaskResponse",
    "Task",
    "TaskState",
    "TaskStatus",
    "TaskSubscriptionEvent",
    "TextPart",
    "TaskManager",
    "build_global_agent_card",
    "build_agent_card",
    "task_event_stream",
]
