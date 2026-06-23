from __future__ import annotations

import httpx
import pytest

from app.api.dependencies import get_db_session
from app.main import app
from app.schemas.agent_tools import (
    EquipmentCheckResponse,
    HealthAnalyzeResponse,
    RecipeRecommendResponse,
    SearchAnswerResponse,
)
from app.services.equipment_agent_service import EquipmentAgentService
from app.services.health_agent_service import HealthAgentService
from app.services.recipe_agent_service import RecipeAgentService
from app.services.search_agent_service import SearchAgentService


class DummyResult:
    """Simulate a SQLAlchemy Result that returns no rows."""
    def scalars(self):
        return self

    def first(self):
        return None

    def all(self):
        return []


class DummySession:
    def execute(self, stmt):
        return DummyResult()

    def close(self) -> None:
        return None


def _override_db_session():
    yield DummySession()


@pytest.mark.asyncio
async def test_mcp_invoke_recipe_recommend_real_route(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_db_session] = _override_db_session

    def _fake_recommend(self, payload):
        return RecipeRecommendResponse(
            title="Dinner Smart Bowl",
            rationale="Based on your target and preferences.",
            estimated_calories=580,
            steps=["prep", "cook", "serve"],
            missing_ingredients=[],
        )

    monkeypatch.setattr(RecipeAgentService, "recommend", _fake_recommend)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/mcp/invoke",
            json={
                "name": "recipe.recommend",
                "input": {
                    "user_id": "u-1",
                    "meal_type": "dinner",
                    "target_calories": 600,
                    "available_equipment": ["pan"],
                    "dietary_preferences": ["high-protein"],
                },
                "user_id": "u-1",
                "action": "invoke",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "recipe.recommend"
    assert payload["result"]["title"] == "Dinner Smart Bowl"
    assert payload["result"]["_audit"]["user_id"] == "u-1"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_invoke_health_analyze_real_route(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_db_session] = _override_db_session

    def _fake_analyze(payload):
        return HealthAnalyzeResponse(
            bmi=22.2,
            bmi_category="normal",
            suggested_daily_calories=2000,
            advice="Maintain balanced meals.",
        )

    monkeypatch.setattr(HealthAgentService, "analyze", staticmethod(_fake_analyze))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/mcp/invoke",
            json={
                "name": "health.analyze",
                "input": {
                    "user_id": "u-1",
                    "height_cm": 175,
                    "weight_kg": 68,
                    "target_weight_kg": 65,
                    "daily_calories_taken": 1900,
                },
                "user_id": "u-1",
                "action": "invoke",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "health.analyze"
    assert payload["result"]["bmi_category"] == "normal"
    assert payload["result"]["_audit"]["action"] == "invoke"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_invoke_equipment_check_real_route(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_db_session] = _override_db_session

    def _fake_check(payload):
        return EquipmentCheckResponse(
            feasible=False,
            missing_equipment=["oven"],
            suggestion="Use a no-oven alternative.",
        )

    monkeypatch.setattr(EquipmentAgentService, "check", staticmethod(_fake_check))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/mcp/invoke",
            json={
                "name": "equipment.check",
                "input": {
                    "equipment_owned": ["pan", "pot"],
                    "required_equipment": ["pan", "oven"],
                },
                "user_id": "u-1",
                "action": "invoke",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "equipment.check"
    assert payload["result"]["feasible"] is False
    assert payload["result"]["missing_equipment"] == ["oven"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_mcp_invoke_search_answer_real_route(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[get_db_session] = _override_db_session

    def _fake_answer(self, payload):
        return SearchAnswerResponse(
            summary="Found memory evidence.",
            evidence=["我不吃花生", "晚餐偏好高蛋白"],
            retrieval_mode="hybrid",
        )

    monkeypatch.setattr(SearchAgentService, "answer", _fake_answer)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/mcp/invoke",
            json={
                "name": "search.answer",
                "input": {
                    "user_id": "u-1",
                    "query": "我的饮食禁忌是什么",
                },
                "user_id": "u-1",
                "action": "invoke",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["tool_name"] == "search.answer"
    assert payload["result"]["retrieval_mode"] == "hybrid"
    assert len(payload["result"]["evidence"]) == 2
    app.dependency_overrides.clear()
