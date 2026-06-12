#!/usr/bin/env python3
"""示例：测试 LangGraph 工作流编排。

演示 Recipe Graph 的多节点执行顺序，使用 Mock Service 隔离外部依赖。

用法：
    python examples/test_workflow.py
"""

from app.schemas.agent_tools import (
    EquipmentCheckRequest,
    EquipmentCheckResponse,
    RecipeRecommendRequest,
    RecipeRecommendResponse,
    SearchAnswerRequest,
    SearchAnswerResponse,
)
from app.services.equipment_agent_service import EquipmentAgentService
from app.services.recipe_agent_service import RecipeAgentService
from app.services.search_agent_service import SearchAgentService
from app.orchestration.agent_graphs import run_recipe_agent


class MockRecipeService(RecipeAgentService):
    """跳过 LLM，返回固定菜谱。"""

    def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        return RecipeRecommendResponse(
            title="测试能量碗",
            rationale="Mock 服务生成的测试菜谱。",
            estimated_calories=500,
            steps=["步骤 1：准备食材", "步骤 2：烹饪", "步骤 3：装盘"],
            required_equipment=["锅", "烤箱", "砧板"],
            missing_ingredients=["测试食材"],
        )


class MockSearchService(SearchAgentService):
    """返回固定记忆证据。"""

    def answer(self, payload: SearchAnswerRequest) -> SearchAnswerResponse:
        return SearchAnswerResponse(
            summary="找到 2 条相关记忆。",
            evidence=["上次做过类似能量碗", "偏好少油烹饪"],
            retrieval_mode="hybrid",
        )


def main() -> None:
    payload = RecipeRecommendRequest(
        user_id="demo",
        meal_type="dinner",
        target_calories=600,
        available_equipment=["锅", "砧板"],
    )

    print("=== Recipe Workflow 测试（Mock Service）===")
    print()
    print("Graph 节点顺序:")
    print("  collect_context → compose → check_equipment → finalize")
    print()

    result = run_recipe_agent(
        payload,
        recipe_service=MockRecipeService(),
        search_service=MockSearchService(),
        equipment_service=EquipmentAgentService(),
    )

    print(f"标题: {result.title}")
    print(f"理由: {result.rationale}")
    print(f"可行: {result.feasible}")
    print(f"缺少厨具: {result.missing_equipment}")
    print()
    print("✓ Graph 完整执行：Search → Recipe → Equipment → Finalize")


if __name__ == "__main__":
    main()
