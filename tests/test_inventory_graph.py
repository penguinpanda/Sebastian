from __future__ import annotations

from app.core.errors import llm_unavailable_message
from app.orchestration.graph import run_inventory_agent


class FakeLLMClient:
    def __init__(self, response: dict[str, object]) -> None:
        self._response = response

    def chat_json(self, messages, temperature: float = 0.2):  # noqa: ANN001
        return self._response


def test_inventory_agent_graph_completes_with_intent(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.orchestration.nodes.get_llm_client",
        lambda: FakeLLMClient(
            {
                "intent": "inventory_summary",
                "action": "summarize inventory",
                "parameters": {},
                "reply": "You have 3 items in inventory.",
            }
        ),
    )

    result = run_inventory_agent(" summarize my inventory ", user_id="u-1")

    assert result == "You have 3 items in inventory."


def test_inventory_agent_graph_falls_back_on_empty_input() -> None:
    result = run_inventory_agent("   ", user_id="u-1")

    assert result == llm_unavailable_message()
