"""测试 Router Agent 意图分类和分发。"""

import pytest

from app.core.errors import LLMError
from app.llm.output_parser import RouterLLMResponse, parse_router_response


def test_parse_router_valid_response() -> None:
    raw = {
        "intent": "recipe",
        "confidence": 0.9,
        "extracted_params": {"meal_type": "dinner"},
        "reasoning": "用户想推荐菜谱",
    }
    result = parse_router_response(raw)
    assert result.intent == "recipe"
    assert result.confidence == 0.9


def test_parse_router_invalid_raises_error() -> None:
    """校验失败时抛出 LLMError，不再静默回退到 general。"""
    with pytest.raises(LLMError):
        parse_router_response({"intent": "invalid_intent"})


def test_parse_router_missing_fields_raises_error() -> None:
    """缺少必要字段时抛出 LLMError。"""
    with pytest.raises(LLMError):
        parse_router_response({})


def test_router_response_all_intents() -> None:
    """所有 6 种意图都应能正确解析。"""
    intents = ["recipe", "health", "inventory", "search", "equipment", "general"]
    for intent in intents:
        result = parse_router_response({"intent": intent, "confidence": 0.8, "reasoning": "test"})
        assert result.intent == intent
