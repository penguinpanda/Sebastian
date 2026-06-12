from __future__ import annotations

from app.orchestration.agent_graphs import run_equipment_agent, run_health_agent, run_recipe_agent, run_search_agent
from app.schemas.agent_tools import (
    EquipmentCheckRequest,
    EquipmentCheckResponse,
    HealthAnalyzeRequest,
    HealthAnalyzeResponse,
    RecipeRecommendRequest,
    RecipeRecommendResponse,
    SearchAnswerRequest,
    SearchAnswerResponse,
)


class FakeRecipeService:
    def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        return RecipeRecommendResponse(
            title="Dinner Smart Bowl",
            rationale="Base rationale.",
            estimated_calories=580,
            steps=["prep", "cook"],
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
