from __future__ import annotations

import logging

from app.llm.client import get_llm_client
from app.llm.output_parser import parse_inventory_response
from app.llm.prompts import build_inventory_messages
from app.orchestration.state import AgentState

logger = logging.getLogger(__name__)


def normalize_input(state: AgentState) -> AgentState:
    """清理用户输入，保证后续节点拿到的是去掉首尾空格的文本。"""
    raw = state.get("user_input", "")
    return {**state, "user_input": raw.strip()}


def classify_intent(state: AgentState) -> AgentState:
    """调用 LLM 识别意图，并把解析后的结构化结果写回状态。"""
    user_input = state.get("user_input", "")
    if not user_input:
        # 空输入不调用模型，直接进入未知意图分支，节省一次外部请求。
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
        # LLM 或解析失败时不中断图执行，交给 fallback 节点返回可控文案。
        logger.warning("Intent classification failed: %s", exc)
        return {**state, "intent": "unknown", "error_state": str(exc)}


def compose_response(state: AgentState) -> AgentState:
    """从 LLM 结构化结果里取出最终回复文本。"""
    llm = state.get("llm_response") or {}
    reply = llm.get("reply") or state.get("error_state") or "Sorry, I could not process your request."
    return {**state, "final_answer": reply}


def fallback_response(state: AgentState) -> AgentState:
    """当意图未知或上游失败时返回安全兜底回复。"""
    return {**state, "final_answer": "I'm not sure how to help with that. Please try rephrasing."}


def _route_intent(state: AgentState) -> str:
    """根据 intent 决定 LangGraph 的下一条边。"""
    intent = state.get("intent", "unknown")
    if intent == "unknown":
        return "fallback"
    return "compose"
