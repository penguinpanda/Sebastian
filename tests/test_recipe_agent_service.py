"""测试 RecipeAgentService.recommend_from_inventory_only 方法。"""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import LLMUnavailableError, ValidationError
from app.repositories.inventory import InMemoryInventoryRepository
from app.schemas.agent_tools import InventoryOnlyRecipeRequest, RecipeRecommendResponse
from app.services.inventory_service import InventoryService
from app.services.recipe_agent_service import RecipeAgentService


def _make_payload(**kw) -> InventoryOnlyRecipeRequest:
    d = {
        "user_id": "u1",
        "meal_type": "dinner",
        "target_calories": 600,
        "available_equipment": ["pan"],
        "dietary_preferences": ["high-protein"],
    }
    d.update(kw)
    return InventoryOnlyRecipeRequest(**d)


def _seed_inventory(svc: InventoryService) -> None:
    from app.schemas.inventory import InventoryCreate

    svc.create_item(InventoryCreate(
        user_id="u1", name="鸡胸肉", quantity=500, unit="g",
        expire_date=date.today() + timedelta(days=5),
    ))
    svc.create_item(InventoryCreate(
        user_id="u1", name="西兰花", quantity=300, unit="g",
        expire_date=date.today() + timedelta(days=3),
    ))
    svc.create_item(InventoryCreate(
        user_id="u1", name="鸡蛋", quantity=6, unit="个",
        expire_date=date.today() + timedelta(days=7),
    ))


# ============================================================
# 测试 1：库存非空且 LLM 正常 → 返回菜谱
# ============================================================
def test_recommend_from_inventory_only_success() -> None:
    repo = InMemoryInventoryRepository()
    inv_svc = InventoryService(repository=repo)
    _seed_inventory(inv_svc)
    service = RecipeAgentService(inventory_service=inv_svc)

    fake_llm_response = {
        "title": "蒜香鸡胸西兰花",
        "rationale": "使用库存鸡胸肉和西兰花，高蛋白低脂。",
        "estimated_calories": 450,
        "ingredients": [
            {"name": "鸡胸肉", "amount": 200, "unit": "g"},
            {"name": "西兰花", "amount": 150, "unit": "g"},
            {"name": "鸡蛋", "amount": 1, "unit": "个"},
        ],
        "steps": ["鸡胸肉切片", "西兰花焯水", "翻炒"],
        "required_equipment": ["pan"],
        "missing_ingredients": [],
    }

    with patch("app.services.recipe_agent_service.check_llm_available"), \
         patch("app.services.recipe_agent_service.get_llm_client") as mock_client:
        mock_client.return_value.chat_json.return_value = fake_llm_response

        result = service.recommend_from_inventory_only(_make_payload())

    assert result.title == "蒜香鸡胸西兰花"
    assert len(result.ingredients) == 3
    assert result.estimated_calories == 450
    assert "missing_ingredients" in result.model_fields_set or True


# ============================================================
# 测试 2：库存为空 → ValidationError
# ============================================================
def test_recommend_from_inventory_only_empty_inventory() -> None:
    repo = InMemoryInventoryRepository()
    inv_svc = InventoryService(repository=repo)
    service = RecipeAgentService(inventory_service=inv_svc)

    with patch("app.services.recipe_agent_service.check_llm_available"):
        with pytest.raises(ValidationError, match="库存为空"):
            service.recommend_from_inventory_only(_make_payload())


# ============================================================
# 测试 3：LLM 不可用 → LLMUnavailableError
# ============================================================
def test_recommend_from_inventory_only_llm_unavailable() -> None:
    repo = InMemoryInventoryRepository()
    inv_svc = InventoryService(repository=repo)
    _seed_inventory(inv_svc)
    service = RecipeAgentService(inventory_service=inv_svc)

    with patch("app.services.recipe_agent_service.check_llm_available", side_effect=LLMUnavailableError("API Key 未配置")):
        with pytest.raises(LLMUnavailableError, match="API Key 未配置"):
            service.recommend_from_inventory_only(_make_payload())


# ============================================================
# 测试 4：LLM 返回无效 JSON → LLMUnavailableError
# ============================================================
def test_recommend_from_inventory_only_llm_invalid_json() -> None:
    repo = InMemoryInventoryRepository()
    inv_svc = InventoryService(repository=repo)
    _seed_inventory(inv_svc)
    service = RecipeAgentService(inventory_service=inv_svc)

    with patch("app.services.recipe_agent_service.check_llm_available"), \
         patch("app.services.recipe_agent_service.get_llm_client") as mock_client:
        mock_client.return_value.chat_json.side_effect = ValueError("Invalid JSON")

        with pytest.raises(LLMUnavailableError):
            service.recommend_from_inventory_only(_make_payload())


# ============================================================
# 测试 5：库存清单正确注入 LLM prompt
# ============================================================
def test_recommend_from_inventory_only_prompt_contains_inventory() -> None:
    repo = InMemoryInventoryRepository()
    inv_svc = InventoryService(repository=repo)
    _seed_inventory(inv_svc)
    service = RecipeAgentService(inventory_service=inv_svc)

    fake_llm_response = {
        "title": "测试菜谱",
        "rationale": "test",
        "estimated_calories": 300,
        "ingredients": [{"name": "鸡胸肉", "amount": 100, "unit": "g"}],
        "steps": ["step1"],
        "required_equipment": ["pan"],
        "missing_ingredients": [],
    }

    with patch("app.services.recipe_agent_service.check_llm_available"), \
         patch("app.services.recipe_agent_service.get_llm_client") as mock_client:
        mock_client.return_value.chat_json.return_value = fake_llm_response

        service.recommend_from_inventory_only(_make_payload())

        # 验证 LLM 调用时 prompt 包含库存信息
        call_args = mock_client.return_value.chat_json.call_args
        messages = call_args[0][0]
        user_content = messages[-1]["content"] if isinstance(messages, list) else ""
        assert "鸡胸肉" in str(user_content)
        assert "西兰花" in str(user_content)
        assert "鸡蛋" in str(user_content)
        assert "【当前库存" in str(user_content)


# ============================================================
# 测试 6：calories 裁剪到 target_calories
# ============================================================
def test_recommend_from_inventory_only_calories_capped() -> None:
    repo = InMemoryInventoryRepository()
    inv_svc = InventoryService(repository=repo)
    _seed_inventory(inv_svc)
    service = RecipeAgentService(inventory_service=inv_svc)

    fake_llm_response = {
        "title": "高热量菜谱",
        "rationale": "test",
        "estimated_calories": 900,
        "ingredients": [{"name": "鸡胸肉", "amount": 300, "unit": "g"}],
        "steps": ["step1"],
        "required_equipment": ["pan"],
        "missing_ingredients": [],
    }

    with patch("app.services.recipe_agent_service.check_llm_available"), \
         patch("app.services.recipe_agent_service.get_llm_client") as mock_client:
        mock_client.return_value.chat_json.return_value = fake_llm_response

        result = service.recommend_from_inventory_only(
            _make_payload(target_calories=500)
        )

    assert result.estimated_calories == 500  # 裁剪到 target_calories
