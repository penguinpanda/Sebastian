"""A2A API 路由 — FastAPI 端点。

提供符合 Google A2A 协议的任务管理端点。

端点:
  GET  /.well-known/agent.json    — 全局 Agent Card
  GET  /a2a/agents/{name}/card    — 单个 Agent Card
  POST /a2a/tasks                 — 创建任务（统一入口）
  GET  /a2a/tasks/{task_id}       — 查询任务状态
  POST /a2a/tasks/{task_id}/subscribe — SSE 流式订阅
  POST /a2a/tasks/{task_id}/cancel    — 取消任务
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.a2a.agent_card import build_agent_card, build_global_agent_card
from app.a2a.client import InternalA2AClient
from app.a2a.schemas import (
    AgentCard,
    CancelTaskResponse,
    Message,
    SendTaskRequest,
    SendTaskResponse,
    Task,
    TaskState,
)
from app.a2a.streaming import build_sse_response
from app.a2a.task_manager import TaskManager, TaskNotFoundError, get_task_manager
from app.agents.recipe_agent import RecipeAgent
from app.agents.health_agent import HealthAgent
from app.agents.search_agent import SearchAgent
from app.agents.equipment_agent import EquipmentAgent
from app.agents.inventory_agent import InventoryAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/a2a", tags=["a2a"])


# ── 全局懒加载 Agent 注册表 ────────────────────────────────────

_agent_registry: dict[str, tuple[AgentCard, object]] | None = None
_a2a_client: InternalA2AClient | None = None


def get_a2a_client() -> InternalA2AClient:
    """获取或初始化内部 A2A 客户端 + Agent 注册。"""
    global _a2a_client, _agent_registry
    if _a2a_client is None:
        _a2a_client = InternalA2AClient()

        # 注册所有 Agent
        _a2a_client.register_agent("recipe", RecipeAgent())
        _a2a_client.register_agent("health", HealthAgent())
        _a2a_client.register_agent("search", SearchAgent())
        _a2a_client.register_agent("equipment", EquipmentAgent())
        _a2a_client.register_agent("inventory", InventoryAgent())

    return _a2a_client


# ── Agent Card 端点 ────────────────────────────────────────────

@router.get("/.well-known/agent.json", response_model=AgentCard, include_in_schema=False)
async def global_agent_card(request: Request) -> AgentCard:
    """全局 Agent Card 端点（符合 A2A well-known 规范）。"""
    base_url = str(request.base_url).rstrip("/")
    return build_global_agent_card(base_url)


@router.get("/agents/{agent_name}/card", response_model=AgentCard)
async def agent_card(agent_name: str, request: Request) -> AgentCard:
    """单个 Agent 的 Agent Card。"""
    base_url = str(request.base_url).rstrip("/")
    try:
        return build_agent_card(agent_name, base_url)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── 任务端点 ───────────────────────────────────────────────────

class ChatLikeRequest(BaseModel):
    """兼容旧前端格式的简化请求体。自动转换为 A2A Message。"""
    message: str = Field(description="用户消息文本")
    user_id: str | None = Field(default=None, description="用户 ID")
    context_id: str | None = Field(default=None, description="会话上下文 ID")
    skill_id: str | None = Field(default=None, description="指定技能（如 'recipe.recommend'）")


@router.post("/tasks", response_model=SendTaskResponse)
async def create_task(
    payload: ChatLikeRequest | SendTaskRequest,
    request: Request,
) -> SendTaskResponse:
    """创建 A2A 任务 — 统一入口。

    支持两种请求格式:
    1. ChatLikeRequest（兼容旧前端）: {"message": "...", "user_id": "..."}
    2. SendTaskRequest（A2A 标准）: {"message": {"role": "user", "parts": [...]}}

    当指定 skill_id 时，直接路由到对应 Agent；
    否则通过 Router 意图识别后分发。
    """
    trace_id = getattr(request.state, "trace_id", None)

    # 统一转换为 A2A 格式
    if isinstance(payload, ChatLikeRequest):
        message = Message.from_text(payload.message)
        context_id = payload.context_id
        skill_id = payload.skill_id
        user_id = payload.user_id
    else:
        message = payload.message
        context_id = payload.context_id
        skill_id = payload.skill_id

    # 记录审计
    request.state.user_id = user_id if "user_id" in dir() else None
    request.state.action = "a2a_create_task"

    client = get_a2a_client()

    if skill_id:
        # 有明确技能指定 → 直接路由到对应 Agent
        agent_name = _resolve_agent_from_skill(skill_id)
        return await client.send_task(
            agent_name=agent_name,
            message=message,
            context_id=context_id,
            blocking=True,
        )
    else:
        # 无技能指定 → Router 意图识别
        from app.agents.router_agent import RouterAgent
        router = RouterAgent(a2a_client=client)
        task = get_task_manager().create_task(message=message, context_id=context_id)
        full_reply: list[str] = []

        async for artifact in router.handle_task(task, message):
            for part in artifact.parts:
                if hasattr(part, "text"):
                    full_reply.append(part.text)

        return SendTaskResponse(task=task, direct_reply="".join(full_reply))


@router.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: str) -> Task:
    """查询 A2A 任务状态。"""
    try:
        return get_task_manager().get_task(task_id)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/tasks/{task_id}/subscribe")
async def subscribe_task(task_id: str) -> Any:
    """SSE 流式订阅任务状态变更。"""
    try:
        get_task_manager().get_task(task_id)  # 检查存在性
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return build_sse_response(task_id)


@router.post("/tasks/{task_id}/cancel", response_model=CancelTaskResponse)
async def cancel_task(task_id: str) -> CancelTaskResponse:
    """取消 A2A 任务。"""
    try:
        canceled = get_task_manager().cancel_task(task_id)
        return CancelTaskResponse(task_id=task_id, canceled=canceled)
    except TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── 辅助 ───────────────────────────────────────────────────────

# Skill ID → Agent 名称映射
SKILL_TO_AGENT = {
    "recipe.recommend": "recipe",
    "recipe.recommend-from-inventory": "recipe",
    "health.analyze": "health",
    "search.answer": "search",
    "equipment.check": "equipment",
    "inventory.query": "inventory",
    "inventory.adjust": "inventory",
    "inventory.expiring": "inventory",
    "inventory.summary": "inventory",
    "router.chat": "router",
}


def _resolve_agent_from_skill(skill_id: str) -> str:
    """根据技能 ID 解析对应的 Agent 名称。"""
    agent_name = SKILL_TO_AGENT.get(skill_id)
    if agent_name is None:
        # 尝试通过 Agent Card 查找
        for name in ("recipe", "health", "search", "equipment", "inventory", "router"):
            card = build_agent_card(name)
            for skill in card.skills:
                if skill.id == skill_id:
                    return name
        raise HTTPException(status_code=400, detail=f"Unknown skill: {skill_id}")
    return agent_name
