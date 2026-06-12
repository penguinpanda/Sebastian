from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.orchestration.nodes import (
    _route_intent,
    classify_intent,
    compose_response,
    fallback_response,
    normalize_input,
)
from app.orchestration.state import AgentState


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
    return result.get("final_answer") or "No response."
