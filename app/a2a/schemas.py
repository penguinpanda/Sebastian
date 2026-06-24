"""A2A 协议 Schema 定义。

对齐 Google Agent-to-Agent Protocol v0.3.0 规范。
所有模型使用 Pydantic v2，支持 JSON Schema 生成和严格校验。

参考: https://github.com/google/A2A/blob/main/specification/a2a_specification.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


# ── 基础枚举 ────────────────────────────────────────────────────────

class TaskState(str, Enum):
    """A2A 任务状态枚举。"""
    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


# ── Agent Card ───────────────────────────────────────────────────────

class AgentSkill(BaseModel):
    """Agent 技能描述，定义该 Agent 能处理的一个任务类型。"""
    id: str = Field(description="技能唯一标识，如 'recipe.recommend'")
    name: str = Field(description="技能人类可读名称")
    description: str = Field(default="", description="技能描述")
    examples: list[str] = Field(default_factory=list, description="示例输入")
    input_schema: dict[str, Any] | None = Field(default=None, description="输入 JSON Schema")
    output_schema: dict[str, Any] | None = Field(default=None, description="输出 JSON Schema")


class AgentCapabilities(BaseModel):
    """Agent 能力声明。"""
    streaming: bool = Field(default=False, description="是否支持 SSE 流式推送")
    push_notifications: bool = Field(default=False, description="是否支持推送通知")
    state_transition_history: bool = Field(default=False, description="是否保留完整状态转换历史")


class AgentCard(BaseModel):
    """Agent Card — A2A 协议的 Agent 自描述元数据。

    通过 GET /.well-known/agent.json 暴露。
    """
    name: str = Field(description="Agent 名称，如 'Recipe Agent'")
    description: str = Field(description="Agent 功能描述")
    url: str = Field(description="Agent 端点 URL，如 'http://localhost:8000/a2a'")
    version: str = Field(default="0.1.0", description="Agent 版本")
    capabilities: AgentCapabilities = Field(default_factory=AgentCapabilities)
    skills: list[AgentSkill] = Field(default_factory=list, description="技能列表")
    default_input_modes: list[str] = Field(default_factory=lambda: ["text"], description="支持的输入模式")
    default_output_modes: list[str] = Field(default_factory=lambda: ["text"], description="支持的输出模式")
    provider: str | None = Field(default=None, description="提供者信息")


# ── Message & Part ───────────────────────────────────────────────────

class TextPart(BaseModel):
    """文本消息片段。"""
    type: Literal["text"] = "text"
    text: str = Field(description="文本内容")


class FilePart(BaseModel):
    """文件消息片段。"""
    type: Literal["file"] = "file"
    url: str = Field(description="文件 URL")
    mime_type: str = Field(default="application/octet-stream", description="MIME 类型")
    name: str | None = Field(default=None, description="文件名")


class DataPart(BaseModel):
    """结构化数据消息片段。"""
    type: Literal["data"] = "data"
    data: dict[str, Any] = Field(default_factory=dict, description="结构化数据载荷")


Part = TextPart | FilePart | DataPart


class Message(BaseModel):
    """A2A 消息，由多个 Part 组成。"""
    role: Literal["user", "agent"] = Field(default="user", description="消息发送者角色")
    parts: list[Part] = Field(default_factory=list, description="消息片段列表")
    message_id: str = Field(default_factory=lambda: str(uuid4()), description="消息唯一 ID")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")

    @property
    def text(self) -> str:
        """便捷属性：拼接所有文本片段。"""
        return "".join(p.text for p in self.parts if isinstance(p, TextPart))

    @classmethod
    def from_text(cls, text: str, role: Literal["user", "agent"] = "user", **kwargs) -> Message:
        """从纯文本便捷创建 Message。"""
        return cls(role=role, parts=[TextPart(text=text)], **kwargs)


# ── Task ─────────────────────────────────────────────────────────────

class TaskStatus(BaseModel):
    """任务状态快照。"""
    state: TaskState = Field(description="当前状态")
    message: str = Field(default="", description="状态说明消息")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Artifact(BaseModel):
    """任务产出。"""
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    parts: list[Part] = Field(default_factory=list, description="产出内容")
    metadata: dict[str, Any] = Field(default_factory=dict, description="产出元数据")
    index: int = Field(default=0, description="产出序号（流式场景）")

    @classmethod
    def from_text(cls, text: str, **kwargs) -> Artifact:
        """从纯文本便捷创建 Artifact。"""
        return cls(parts=[TextPart(text=text)], **kwargs)


class Task(BaseModel):
    """A2A 任务 — 工作单元的核心抽象。"""
    id: str = Field(default_factory=lambda: str(uuid4()), description="任务唯一 ID")
    context_id: str | None = Field(default=None, description="会话上下文 ID（多轮对话关联）")
    status: TaskStatus = Field(default_factory=lambda: TaskStatus(state=TaskState.SUBMITTED))
    artifacts: list[Artifact] = Field(default_factory=list, description="任务产出列表")
    history: list[Message] = Field(default_factory=list, description="该任务的消息历史")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Request / Response ───────────────────────────────────────────────

class SendTaskRequest(BaseModel):
    """创建 A2A 任务的请求体。"""
    message: Message = Field(description="用户消息")
    context_id: str | None = Field(default=None, description="会话上下文 ID")
    skill_id: str | None = Field(default=None, description="指定调用的技能 ID（可选）")
    blocking: bool = Field(default=True, description="是否阻塞等待完成")
    accepted_output_modes: list[str] = Field(default_factory=lambda: ["text"], description="期望输出格式")
    metadata: dict[str, Any] = Field(default_factory=dict, description="请求级元数据")


class SendTaskResponse(BaseModel):
    """创建 A2A 任务的响应体。"""
    task: Task = Field(description="创建的任务")
    direct_reply: str | None = Field(default=None, description="阻塞模式下的直接回复文本")


class CancelTaskResponse(BaseModel):
    """取消 A2A 任务的响应体。"""
    task_id: str = Field(description="任务 ID")
    canceled: bool = Field(default=True, description="是否成功取消")


# ── SSE 事件 ─────────────────────────────────────────────────────────

class TaskSubscriptionEvent(BaseModel):
    """SSE 推送的任务状态变更事件。"""
    task_id: str = Field(description="任务 ID")
    status: TaskStatus = Field(description="新状态")
    artifact: Artifact | None = Field(default=None, description="增量产出（流式场景）")
    final: bool = Field(default=False, description="是否为最终事件（任务结束）")
