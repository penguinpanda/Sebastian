"""Recipe Agent — A2A 兼容的菜谱推荐助手。

集成搜索记忆、厨具检查和 LLM 菜谱生成。
保留现有 4 步 LangGraph 图编排逻辑。
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.a2a.schemas import AgentCard, Artifact, Message, Task
from app.agents.base import BaseAgent
from app.context.budget import ContextBudget
from app.schemas.agent_tools import (
    InventoryOnlyRecipeRequest,
    RecipeRecommendRequest,
    RecipeRecommendResponse,
)
from app.services.recipe_agent_service import RecipeAgentService

logger = logging.getLogger(__name__)


class RecipeAgent(BaseAgent):
    """菜谱推荐 Agent。

    流程: collect_context（搜索+库存）→ compose（LLM 生成）→ check_equipment → finalize。
    """

    agent_card = AgentCard(
        name="Recipe Agent",
        description="菜谱推荐助手 — 根据用户需求、库存食材和饮食偏好推荐菜谱",
        url="http://localhost:8000/a2a",
    )

    def __init__(self, service: RecipeAgentService | None = None) -> None:
        super().__init__()
        self._service = service or RecipeAgentService()

    # ── 兼容旧接口 ──────────────────────────────────────────────

    def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        """旧同步接口兼容层。"""
        from app.orchestration.agent_graphs import run_recipe_agent
        return run_recipe_agent(payload, recipe_service=self._service)

    def recommend_from_inventory(self, payload: InventoryOnlyRecipeRequest) -> RecipeRecommendResponse:
        """旧同步接口兼容层。"""
        from app.orchestration.agent_graphs import run_recipe_agent_inventory_only
        return run_recipe_agent_inventory_only(payload, recipe_service=self._service)

    # ── A2A 接口 ────────────────────────────────────────────────

    async def execute(
        self,
        task: Task,
        message: Message,
        llm_messages: list[dict[str, str]],
        budget: ContextBudget,
    ) -> AsyncIterator[Artifact]:
        """A2A 异步处理入口。"""
        params = self._extract_skill_params(message)
        user_id = message.metadata.get("user_id", params.get("user_id", "default"))
        user_text = message.text

        # 判断是否为纯库存模式
        skill_id = message.metadata.get("skill_id", params.get("skill_id", ""))

        if skill_id == "recipe.recommend-from-inventory":
            yield Artifact.from_text("正在分析库存食材...")
            result = self._service.recommend_from_inventory_only(
                InventoryOnlyRecipeRequest(user_id=user_id)
            )
        else:
            yield Artifact.from_text("正在搜索相关记忆和菜谱...")
            result = self._service.recommend(
                RecipeRecommendRequest(
                    user_id=user_id,
                    meal_type=params.get("meal_type", "lunch"),
                    target_calories=params.get("target_calories", 500),
                    available_equipment=params.get("available_equipment", []),
                    dietary_preferences=params.get("dietary_preferences", []),
                )
            )

        # 构建结构化输出
        reply_parts = [f"🍽️ {result.title}"]
        if result.rationale:
            reply_parts.append(f"📝 {result.rationale}")
        if result.estimated_calories:
            reply_parts.append(f"🔥 约 {result.estimated_calories} kcal")
        if result.ingredients:
            reply_parts.append("📋 食材：")
            for ing in result.ingredients:
                reply_parts.append(f"  • {ing.name} {ing.amount}{ing.unit}")
        if result.steps:
            reply_parts.append("👨‍🍳 步骤：")
            for i, step in enumerate(result.steps, 1):
                reply_parts.append(f"  {i}. {step}")

        yield Artifact.from_text(
            "\n".join(reply_parts),
            metadata={
                "title": result.title,
                "estimated_calories": result.estimated_calories,
                "ingredients": [{"name": i.name, "amount": i.amount, "unit": i.unit} for i in result.ingredients],
                "steps": result.steps,
                "required_equipment": result.required_equipment,
            },
        )
