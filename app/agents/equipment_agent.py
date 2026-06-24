"""Equipment Agent — A2A 兼容的厨具检查助手。

检查菜谱所需厨具与用户拥有厨具的匹配情况，并用 LLM 生成替代建议。
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from app.a2a.schemas import AgentCard, Artifact, Message, Task
from app.agents.base import BaseAgent
from app.context.budget import ContextBudget
from app.core.errors import LLMUnavailableError
from app.llm.client import check_llm_available, get_llm_client

logger = logging.getLogger(__name__)


class EquipmentAgent(BaseAgent):
    """厨具检查 Agent。"""

    agent_card = AgentCard(
        name="Equipment Agent",
        description="厨具顾问 — 检查所需厨具是否完备，给出替代方案建议",
        url="http://localhost:8000/a2a",
    )

    # ── 兼容旧接口 ──────────────────────────────────────────────

    def check(self, payload):
        """旧同步接口兼容层。"""
        from app.orchestration.agent_graphs import run_equipment_agent
        return run_equipment_agent(payload)

    # ── A2A 接口 ────────────────────────────────────────────────

    async def execute(
        self,
        task: Task,
        message: Message,
        llm_messages: list[dict[str, str]],
        budget: ContextBudget,
    ) -> AsyncIterator[Artifact]:
        """A2A 异步处理入口。"""
        params = self._extract_skill_params(message)
        owned = params.get("equipment_owned", [])
        required = params.get("required_equipment", [])

        owned_set = {item.strip().lower() for item in owned if item.strip()}
        required_set = {item.strip().lower() for item in required if item.strip()}
        missing = sorted(required_set - owned_set)

        suggestion = self._generate_suggestion(
            owned=list(owned_set), missing=missing, required=list(required_set),
        )

        result_text = (
            f"厨具检查结果：\n"
            f"已拥有：{'、'.join(owned_set) if owned_set else '无'}\n"
            f"缺少：{'、'.join(missing) if missing else '无'}\n"
            f"建议：{suggestion}"
        )

        yield Artifact.from_text(
            result_text,
            metadata={
                "feasible": len(missing) == 0,
                "missing_equipment": missing,
                "suggestion": suggestion,
            },
        )

    @staticmethod
    def _generate_suggestion(owned: list[str], missing: list[str], required: list[str]) -> str:
        """调用 LLM 生成厨具建议。"""
        check_llm_available()

        owned_str = "、".join(owned) if owned else "无"
        missing_str = "、".join(missing) if missing else "无"
        required_str = "、".join(required) if required else "无"

        messages = [
            {"role": "system", "content": "你是厨具顾问。给出实用建议（替代方案、免烹饪选择等）。用中文，100字以内。"},
            {"role": "user", "content": f"已有：{owned_str}\n缺少：{missing_str}\n所需：{required_str}\n请给出建议。"},
        ]

        try:
            return get_llm_client().chat(messages, temperature=0.4, max_tokens=200)
        except Exception as exc:
            logger.warning("Equipment suggestion LLM failed: %s", exc)
            if missing:
                return f"缺少厨具：{'、'.join(missing)}。建议：可考虑替代方案或选择无需这些厨具的菜谱。"
            return "厨具齐全，可以开始烹饪！"
