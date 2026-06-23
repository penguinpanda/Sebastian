from __future__ import annotations

import logging
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.core.errors import llm_unavailable_message
from app.llm.client import get_llm_client
from app.llm.prompts import build_general_messages, SYSTEM_GENERAL
from app.orchestration.nodes import (
    _route_intent,
    classify_intent,
    classify_router_intent,
    compose_response,
    fallback_response,
    normalize_input,
)
from app.orchestration.state import AgentState

logger = logging.getLogger(__name__)


def _build_normalize_subgraph() -> StateGraph:
    """输入清洗子图：把用户原文整理成下游节点可直接消费的状态。"""
    graph = StateGraph(AgentState)
    graph.add_node("normalize_input", normalize_input)
    graph.add_edge(START, "normalize_input")
    graph.add_edge("normalize_input", END)
    return graph


def _build_intent_subgraph() -> StateGraph:
    """意图识别子图：调用 LLM，把自然语言映射成结构化 intent。"""
    graph = StateGraph(AgentState)
    graph.add_node("classify_intent", classify_intent)
    graph.add_edge(START, "classify_intent")
    graph.add_edge("classify_intent", END)
    return graph


def _dispatch_response(state: AgentState) -> AgentState:
    # 这个节点只作为条件分发锚点，实际路由由 _route_intent 决定。
    return state


def _build_response_subgraph() -> StateGraph:
    """回复生成子图：已识别意图走正常回复，未知意图走兜底回复。"""
    graph = StateGraph(AgentState)
    graph.add_node("dispatch_response", _dispatch_response)
    graph.add_node("compose_response", compose_response)
    graph.add_node("fallback_response", fallback_response)
    graph.add_edge(START, "dispatch_response")
    graph.add_conditional_edges("dispatch_response", _route_intent, {"compose": "compose_response", "fallback": "fallback_response"})
    graph.add_edge("compose_response", END)
    graph.add_edge("fallback_response", END)
    return graph


def build_inventory_graph() -> StateGraph:
    """组装库存 Agent 的主流程：清洗输入 -> 识别意图 -> 生成回复。"""
    graph = StateGraph(AgentState)

    graph.add_node("normalize_stage", _build_normalize_subgraph().compile())
    graph.add_node("intent_stage", _build_intent_subgraph().compile())
    graph.add_node("response_stage", _build_response_subgraph().compile())

    graph.add_edge(START, "normalize_stage")
    graph.add_edge("normalize_stage", "intent_stage")
    graph.add_edge("intent_stage", "response_stage")
    graph.add_edge("response_stage", END)

    return graph


@lru_cache(maxsize=1)
def get_compiled_graph():
    """LangGraph 编译有成本，进程内缓存一份即可复用。"""
    return build_inventory_graph().compile()


def run_inventory_agent(user_input: str, user_id: str | None = None) -> str:
    """运行库存意图图，并返回最终回复文本。"""
    compiled = get_compiled_graph()
    result: AgentState = compiled.invoke({"user_input": user_input, "user_id": user_id})
    return result.get("final_answer") or llm_unavailable_message()


# ---- Router Agent: 全局意图分发 ----

def _dispatch_agent(state: AgentState) -> AgentState:
    """根据 router intent 调用对应 Agent 生成回复。"""
    intent = state.get("intent", "general")
    user_input = state.get("user_input", "")
    user_id = state.get("user_id")

    try:
        client = get_llm_client()

        if intent == "recipe":
            messages = [
                {"role": "system", "content": (
                    "你是菜谱助手。根据用户需求推荐一道菜谱，用中文回复。"
                    "简洁说明菜名、热量、主要食材和步骤。"
                )},
                {"role": "user", "content": user_input},
            ]
            reply = client.chat(messages, temperature=0.5, max_tokens=500)

        elif intent == "health":
            messages = [
                {"role": "system", "content": (
                    "你是健康分析助手。根据用户提供的信息给出健康建议，用中文回复。"
                    "如需 BMI 计算请提醒用户提供身高体重。"
                )},
                {"role": "user", "content": user_input},
            ]
            reply = client.chat(messages, temperature=0.4, max_tokens=400)

        elif intent == "inventory":
            # 委托现有库存 Agent
            reply = run_inventory_agent(user_input, user_id=user_id)

        elif intent == "search":
            messages = [
                {"role": "system", "content": (
                    "你是知识搜索助手。回答用户问题，用中文回复，简洁准确。"
                )},
                {"role": "user", "content": user_input},
            ]
            reply = client.chat(messages, temperature=0.4, max_tokens=400)

        elif intent == "equipment":
            messages = [
                {"role": "system", "content": (
                    "你是厨具顾问。根据用户问题提供厨具建议，用中文回复。"
                )},
                {"role": "user", "content": user_input},
            ]
            reply = client.chat(messages, temperature=0.4, max_tokens=300)

        else:  # general
            messages = build_general_messages(user_input)
            reply = client.chat(messages, temperature=0.5, max_tokens=400)

    except Exception as exc:
        logger.warning("Agent dispatch failed for intent=%s: %s", intent, exc)
        reply = llm_unavailable_message()

    return {**state, "final_answer": reply}


def _build_router_graph() -> StateGraph:
    """全局路由图：清洗输入 → 识别意图 → 分发 Agent → 返回回复。"""
    graph = StateGraph(AgentState)

    graph.add_node("normalize", normalize_input)
    graph.add_node("classify_router", classify_router_intent)
    graph.add_node("dispatch_agent", _dispatch_agent)

    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "classify_router")
    graph.add_edge("classify_router", "dispatch_agent")
    graph.add_edge("dispatch_agent", END)

    return graph


@lru_cache(maxsize=1)
def get_router_graph():
    return _build_router_graph().compile()


def run_router_agent(user_input: str, user_id: str | None = None) -> str:
    """全局路由入口：识别意图 → 分发 Agent → 返回回复。"""
    compiled = get_router_graph()
    result: AgentState = compiled.invoke({"user_input": user_input, "user_id": user_id})
    return result.get("final_answer") or llm_unavailable_message()
