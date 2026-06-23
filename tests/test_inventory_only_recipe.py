"""测试 POST /api/agents/recipe/recommend-from-inventory 端点。"""

from datetime import date, timedelta
from unittest.mock import patch

import httpx
import pytest

from app.api.routes.agent_tools import get_recipe_agent
from app.core.errors import LLMUnavailableError, ValidationError
from app.main import app
from app.schemas.agent_tools import InventoryOnlyRecipeRequest, RecipeRecommendResponse


def _make_payload(**kw) -> dict:
    d = {
        "user_id": "u1",
        "meal_type": "dinner",
        "target_calories": 600,
        "available_equipment": ["pan"],
        "dietary_preferences": ["high-protein"],
    }
    d.update(kw)
    return d


# ============================================================
# 测试 1：正常请求 → 200 + RecipeRecommendResponse
# ============================================================
@pytest.mark.asyncio
async def test_recommend_from_inventory_endpoint_success() -> None:
    class StubRecipeAgent:
        def recommend_from_inventory(self, payload):
            return RecipeRecommendResponse(
                title="库存菜谱测试",
                rationale="仅使用库存食材。",
                estimated_calories=500,
                ingredients=[
                    {"name": "鸡胸肉", "amount": 200, "unit": "g"},
                ],
                steps=["步骤1", "步骤2"],
                required_equipment=["pan"],
                feasible=True,
                missing_equipment=[],
                missing_ingredients=[],
            )

    app.dependency_overrides[get_recipe_agent] = lambda: StubRecipeAgent()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/agents/recipe/recommend-from-inventory",
            json=_make_payload(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "库存菜谱测试"
    assert len(data["ingredients"]) == 1
    assert data["ingredients"][0]["name"] == "鸡胸肉"
    app.dependency_overrides.clear()


# ============================================================
# 测试 2：库存为空 → 400
# ============================================================
@pytest.mark.asyncio
async def test_recommend_from_inventory_endpoint_empty_inventory() -> None:
    class StubRecipeAgentEmpty:
        def recommend_from_inventory(self, payload):
            raise ValidationError("库存为空，无法仅使用库存材料生成菜谱。请先添加库存食材。")

    app.dependency_overrides[get_recipe_agent] = lambda: StubRecipeAgentEmpty()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/agents/recipe/recommend-from-inventory",
            json=_make_payload(),
        )

    assert response.status_code == 400
    data = response.json()
    assert data["success"] is False
    assert "库存为空" in data["error"]
    app.dependency_overrides.clear()


# ============================================================
# 测试 3：LLM 不可用 → 503
# ============================================================
@pytest.mark.asyncio
async def test_recommend_from_inventory_endpoint_llm_unavailable() -> None:
    class StubRecipeAgentLLMDown:
        def recommend_from_inventory(self, payload):
            raise LLMUnavailableError("DeepSeek API Key 未配置")

    app.dependency_overrides[get_recipe_agent] = lambda: StubRecipeAgentLLMDown()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/agents/recipe/recommend-from-inventory",
            json=_make_payload(),
        )

    assert response.status_code == 503
    data = response.json()
    assert data["success"] is False
    assert "LLM" in data["error"] or "API Key" in data["error"]
    app.dependency_overrides.clear()


# ============================================================
# 测试 4：请求参数校验 → 422
# ============================================================
@pytest.mark.asyncio
async def test_recommend_from_inventory_endpoint_validation() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 缺少必填字段 user_id
        response = await client.post(
            "/api/agents/recipe/recommend-from-inventory",
            json={"meal_type": "dinner"},
        )

    assert response.status_code == 422


# ============================================================
# 测试 5：target_calories 超出范围 → 422
# ============================================================
@pytest.mark.asyncio
async def test_recommend_from_inventory_endpoint_calories_out_of_range() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/agents/recipe/recommend-from-inventory",
            json=_make_payload(target_calories=3000),
        )

    assert response.status_code == 422
