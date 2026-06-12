from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    user_input: str
    user_id: str | None
    intent: str | None
    llm_response: dict | None
    tool_results: list[dict]
    final_answer: str | None
    error_state: str | None
