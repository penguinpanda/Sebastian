from __future__ import annotations

import httpx
import pytest

from app.api.routes.agent_tools import get_equipment_agent, get_health_agent, get_recipe_agent, get_search_agent
from app.main import app


@pytest.mark.asyncio
async def test_recipe_agent_endpoint() -> None:
    class StubRecipeAgent:
        def recommend(self, payload):
            return {
                "title": "Dinner Smart Bowl",
                "rationale": "Based on inventory and target calories.",
                "estimated_calories": 520,
                "steps": ["step1", "step2"],
                "missing_ingredients": [],
            }

    app.dependency_overrides[get_recipe_agent] = lambda: StubRecipeAgent()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/agents/recipe/recommend",
            json={
                "user_id": "u-1",
                "meal_type": "dinner",
                "target_calories": 600,
                "available_equipment": ["pan"],
                "dietary_preferences": ["high-protein"],
            },
        )

    assert response.status_code == 200
    assert response.json()["title"] == "Dinner Smart Bowl"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health_agent_endpoint() -> None:
    class StubHealthAgent:
        def analyze(self, payload, meal_history=None, days=7):
            return {
                "bmi": 22.1,
                "bmi_category": "normal",
                "suggested_daily_calories": 2000,
                "advice": "Maintain balanced meals.",
            }

    app.dependency_overrides[get_health_agent] = lambda: StubHealthAgent()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/agents/health/analyze",
            json={
                "user_id": "u-1",
                "height_cm": 175,
                "weight_kg": 68,
                "daily_calories_taken": 1900,
            },
        )

    assert response.status_code == 200
    assert response.json()["bmi_category"] == "normal"
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_equipment_agent_endpoint() -> None:
    class StubEquipmentAgent:
        def check(self, payload):
            return {
                "feasible": False,
                "missing_equipment": ["oven"],
                "suggestion": "Use pan-only recipes.",
            }

    app.dependency_overrides[get_equipment_agent] = lambda: StubEquipmentAgent()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/agents/equipment/check",
            json={"equipment_owned": ["pan"], "required_equipment": ["pan", "oven"]},
        )

    assert response.status_code == 200
    assert response.json()["feasible"] is False
    assert response.json()["missing_equipment"] == ["oven"]
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_search_agent_endpoint() -> None:
    class StubSearchAgent:
        def answer(self, payload):
            return {
                "summary": "Found memory evidence.",
                "evidence": ["avoid peanuts"],
                "retrieval_mode": "hybrid",
            }

    app.dependency_overrides[get_search_agent] = lambda: StubSearchAgent()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/agents/search/answer",
            json={"user_id": "u-1", "query": "有什么饮食禁忌"},
        )

    assert response.status_code == 200
    assert response.json()["retrieval_mode"] == "hybrid"
    app.dependency_overrides.clear()
