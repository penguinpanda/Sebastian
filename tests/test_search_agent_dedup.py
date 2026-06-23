"""测试 SearchAgentService 菜谱去重逻辑。"""

import pytest
from unittest.mock import MagicMock, patch

from app.schemas.agent_tools import RecipeIngredient, RecipeRecommendResponse
from app.services.search_agent_service import SearchAgentService


def make_recipe(title: str, ingredients: list[tuple[str, float, str]]) -> RecipeRecommendResponse:
    return RecipeRecommendResponse(
        title=title,
        rationale="test",
        estimated_calories=500,
        ingredients=[RecipeIngredient(name=n, amount=a, unit=u) for n, a, u in ingredients],
        steps=["step1"],
    )


def test_recipe_similarity_exact_match() -> None:
    """标题完全匹配的菜谱相似度应为 0.9。"""
    recipe = make_recipe("宫保鸡丁", [("鸡胸肉", 200, "g"), ("花生", 50, "g")])
    existing = "【菜谱】宫保鸡丁（约600kcal）"
    assert SearchAgentService._recipe_similarity(recipe, existing) == 0.9


def test_recipe_similarity_partial_match() -> None:
    """配料部分匹配应返回对应比例。"""
    recipe = make_recipe("沙拉", [("生菜", 100, "g"), ("番茄", 50, "g"), ("黄瓜", 50, "g")])
    existing = "【菜谱】田园沙拉 配料：生菜、番茄"
    sim = SearchAgentService._recipe_similarity(recipe, existing)
    assert sim > 0.6
    assert sim < 1.0


def test_recipe_similarity_no_match() -> None:
    """完全不匹配的菜谱相似度为 0。"""
    recipe = make_recipe("牛排", [("牛肉", 300, "g")])
    existing = "完全不相关的内容"
    assert SearchAgentService._recipe_similarity(recipe, existing) == 0.0


def test_save_recipe_memory_duplicate() -> None:
    """重复菜谱应被检测为 is_duplicate=True。"""
    mock_search = MagicMock()
    mock_search.search_memory.return_value = MagicMock()
    mock_search.search_memory.return_value.hits = [
        MagicMock(memory_id="existing-1", content="【菜谱】宫保鸡丁（约600kcal）\n配料：鸡胸肉200g、花生50g"),
    ]

    service = SearchAgentService(search_service=mock_search)
    recipe = make_recipe("宫保鸡丁", [("鸡胸肉", 200, "g"), ("花生", 50, "g")])

    memory_id, is_dup = service.save_recipe_memory("u1", recipe)
    assert is_dup is True
    assert memory_id == "existing-1"
