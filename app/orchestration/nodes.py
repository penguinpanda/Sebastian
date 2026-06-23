from __future__ import annotations

import logging

from app.core.errors import llm_unavailable_message
from app.llm.client import get_llm_client
from app.llm.output_parser import parse_inventory_response, parse_router_response
from app.llm.prompts import build_inventory_messages, build_router_messages
from app.orchestration.state import AgentState

logger = logging.getLogger(__name__)


def normalize_input(state: AgentState) -> AgentState:
    """清理用户输入，保证后续节点拿到的是去掉首尾空格的文本。"""
    raw = state.get("user_input", "")
    return {**state, "user_input": raw.strip()}


def classify_router_intent(state: AgentState) -> AgentState:
    """全局意图路由器：识别用户消息应由哪个 Agent 处理（recipe/health/inventory/search/equipment/general）。"""
    user_input = state.get("user_input", "")
    if not user_input:
        return {**state, "intent": "general", "error_state": "empty input"}

    try:
        client = get_llm_client()
        messages = build_router_messages(user_input)
        raw = client.chat_json(messages, temperature=0.2, max_tokens=300)
        parsed = parse_router_response(raw)
        return {
            **state,
            "intent": parsed.intent,
            "llm_response": {"router": parsed.model_dump()},
        }
    except Exception as exc:
        logger.warning("Router intent classification failed: %s", exc)
        return {**state, "intent": "general", "error_state": f"llm_unavailable: {exc}"}


def classify_intent(state: AgentState) -> AgentState:
    """调用 LLM 识别意图，并把解析后的结构化结果写回状态。"""
    user_input = state.get("user_input", "")
    if not user_input:
        return {**state, "intent": "unknown", "error_state": "empty input"}

    try:
        client = get_llm_client()
        messages = build_inventory_messages(user_input)
        raw = client.chat_json(messages, temperature=0.2)
        parsed = parse_inventory_response(raw)
        return {
            **state,
            "intent": parsed.intent,
            "llm_response": parsed.model_dump(),
        }
    except Exception as exc:
        logger.warning("Intent classification failed: %s", exc)
        return {**state, "intent": "unknown", "error_state": f"llm_unavailable: {exc}"}


def compose_response(state: AgentState) -> AgentState:
    """从 LLM 结构化结果里取出最终回复文本。

    LLM 不可用时返回统一错误消息，绝不生成模拟回复。
    """
    error_state = state.get("error_state", "")
    if error_state and "llm_unavailable" in error_state:
        return {**state, "final_answer": llm_unavailable_message()}

    llm = state.get("llm_response") or {}
    reply = llm.get("reply")
    if not reply:
        return {**state, "final_answer": llm_unavailable_message()}
    return {**state, "final_answer": reply}


def fallback_response(state: AgentState) -> AgentState:
    """当意图未知或上游失败时，返回统一的 LLM 不可用错误。"""
    return {**state, "final_answer": llm_unavailable_message()}


def _route_intent(state: AgentState) -> str:
    """根据 intent 决定 LangGraph 的下一条边。"""
    intent = state.get("intent", "unknown")
    error_state = state.get("error_state", "")
    if intent == "unknown" or "llm_unavailable" in error_state:
        return "fallback"
    return "compose"
