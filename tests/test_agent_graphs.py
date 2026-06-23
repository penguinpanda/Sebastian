from __future__ import annotations

from app.orchestration.agent_graphs import (
    run_equipment_agent,
    run_health_agent,
    run_recipe_agent,
    run_recipe_agent_inventory_only,
    run_search_agent,
)
from app.schemas.agent_tools import (
    EquipmentCheckRequest,
    EquipmentCheckResponse,
    HealthAnalyzeRequest,
    HealthAnalyzeResponse,
    InventoryOnlyRecipeRequest,
    RecipeRecommendRequest,
    RecipeRecommendResponse,
    SearchAnswerRequest,
    SearchAnswerResponse,
)


# Test doubles (Fake services) are legitimate test infrastructure used to
# isolate graph orchestration tests from real LLM calls. They simulate the
# interface contract of each service without generating real LLM output.


class FakeRecipeService:
    def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        return RecipeRecommendResponse(
            title="Dinner Smart Bowl",
            rationale="Based on your preferences and available ingredients.",
            estimated_calories=580,
            ingredients=[],
            steps=["prep", "cook"],
            required_equipment=["pan"],
            missing_ingredients=["tofu"],
        )


class FakeSearchService:
    def answer(self, payload: SearchAnswerRequest) -> SearchAnswerResponse:
        return SearchAnswerResponse(
            summary="Found memory evidence.",
            evidence=["avoid peanuts", "prefer high-protein dinner"],
            retrieval_mode="hybrid",
        )


class FakeEquipmentService:
    def check(self, payload: EquipmentCheckRequest) -> EquipmentCheckResponse:
        return EquipmentCheckResponse(
            feasible=False,
            missing_equipment=["oven"],
            suggestion="Use a pan-only alternative.",
        )


class FakeHealthService:
    @staticmethod
    def analyze(payload: HealthAnalyzeRequest) -> HealthAnalyzeResponse:
        return HealthAnalyzeResponse(
            bmi=22.1,
            bmi_category="normal",
            suggested_daily_calories=2000,
            advice="Maintain balanced meals.",
        )


def test_recipe_graph_composes_subgraph_context() -> None:
    result = run_recipe_agent(
        RecipeRecommendRequest(
            user_id="u-1",
            meal_type="dinner",
            target_calories=600,
            available_equipment=["pan"],
            dietary_preferences=["high-protein"],
        ),
        recipe_service=FakeRecipeService(),
        search_service=FakeSearchService(),
        equipment_service=FakeEquipmentService(),
    )

    assert result.title == "Dinner Smart Bowl"
    assert "记忆提示" in result.rationale
    assert "avoid peanuts" in result.rationale
    assert "oven" not in result.missing_ingredients
    assert not any("缺少以下厨具" in step for step in result.steps)


def test_health_graph_returns_health_result() -> None:
    result = run_health_agent(
        HealthAnalyzeRequest(user_id="u-1", height_cm=175, weight_kg=68, daily_calories_taken=1900),
        service=FakeHealthService(),
    )

    assert result.bmi_category == "normal"
    assert result.advice == "Maintain balanced meals."


def test_equipment_graph_returns_equipment_result() -> None:
    result = run_equipment_agent(
        EquipmentCheckRequest(equipment_owned=["pan"], required_equipment=["pan", "oven"]),
        service=FakeEquipmentService(),
    )

    assert result.feasible is False
    assert result.missing_equipment == ["oven"]


def test_search_graph_returns_search_result() -> None:
    result = run_search_agent(
        SearchAnswerRequest(user_id="u-1", query="我的饮食禁忌是什么"),
        service=FakeSearchService(),
    )

    assert result.retrieval_mode == "hybrid"
    assert len(result.evidence) == 2


class FakeRecipeServiceInventoryOnly:
    """Fake service for inventory-only recipe graph tests."""

    def recommend_from_inventory_only(
        self, payload: InventoryOnlyRecipeRequest
    ) -> RecipeRecommendResponse:
        return RecipeRecommendResponse(
            title="库存限定菜谱",
            rationale="仅使用库存食材生成。",
            estimated_calories=450,
            ingredients=[
                {"name": "鸡胸肉", "amount": 200, "unit": "g"},
                {"name": "西兰花", "amount": 150, "unit": "g"},
            ],
            steps=["准备食材", "翻炒"],
            required_equipment=["pan"],
            missing_ingredients=[],
        )


def test_recipe_graph_inventory_only() -> None:
    """验证仅库存菜谱图跳过搜索记忆和厨具检查，直接调用 Service。"""
    result = run_recipe_agent_inventory_only(
        InventoryOnlyRecipeRequest(
            user_id="u-1",
            meal_type="dinner",
            target_calories=600,
            available_equipment=["pan"],
            dietary_preferences=["high-protein"],
        ),
        recipe_service=FakeRecipeServiceInventoryOnly(),
    )

    assert result.title == "库存限定菜谱"
    assert len(result.ingredients) == 2
    assert result.ingredients[0].name == "鸡胸肉"
    # 库存仅模式不应包含搜索记忆提示
    assert "记忆提示" not in result.rationale
