from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError as PydanticValidationError

from app.core.errors import LLMError


class InventoryLLMResponse(BaseModel):
    intent: Literal[
        "inventory_query",
        "inventory_adjust",
        "inventory_expiring",
        "inventory_summary",
    ]
    action: str = Field(min_length=1, max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)
    reply: str = Field(min_length=1, max_length=2000)


class RouterLLMResponse(BaseModel):
    """全局意图分类：识别用户请求应该由哪个 Agent 处理。"""
    intent: Literal[
        "recipe",       # 菜谱推荐 / 吃什么 / 怎么做
        "health",       # 健康分析 / BMI / 饮食评估
        "inventory",    # 库存查询 / 添加 / 调整 / 过期
        "search",       # 知识搜索 / 通用问答
        "equipment",    # 厨具检查
        "general",      # 闲聊 / 无法归类
    ]
    confidence: float = Field(default=0.8, ge=0, le=1)
    extracted_params: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = Field(default="", max_length=500)


def parse_router_response(raw: dict[str, Any]) -> RouterLLMResponse:
    """解析 LLM 返回的意图分类结果。

    校验失败时抛出 LLMError，因为这意味着 LLM 返回了不符合预期的格式，
    不应静默回退到 general 意图。
    """
    try:
        return RouterLLMResponse.model_validate(raw)
    except PydanticValidationError as exc:
        raise LLMError(f"Router LLM response failed schema validation: {exc}") from exc


def parse_inventory_response(raw: dict[str, Any]) -> InventoryLLMResponse:
    try:
        return InventoryLLMResponse.model_validate(raw)
    except PydanticValidationError as exc:
        raise LLMError(f"LLM response failed schema validation: {exc}") from exc
