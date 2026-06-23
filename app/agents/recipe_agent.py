from __future__ import annotations

from app.schemas.agent_tools import (
    InventoryOnlyRecipeRequest,
    RecipeRecommendRequest,
    RecipeRecommendResponse,
)
from app.services.recipe_agent_service import RecipeAgentService
from app.orchestration.agent_graphs import run_recipe_agent, run_recipe_agent_inventory_only


class RecipeAgent:
    def __init__(self, service: RecipeAgentService | None = None) -> None:
        self._service = service or RecipeAgentService()

    def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        return run_recipe_agent(payload, recipe_service=self._service)

    def recommend_from_inventory(
        self, payload: InventoryOnlyRecipeRequest
    ) -> RecipeRecommendResponse:
        """仅使用库存材料生成菜谱：跳过搜索记忆和厨具检查子图，直接调用 Service。"""
        return run_recipe_agent_inventory_only(payload, recipe_service=self._service)
