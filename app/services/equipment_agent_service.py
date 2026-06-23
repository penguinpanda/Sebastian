from __future__ import annotations

import logging

from app.core.errors import LLMUnavailableError
from app.llm.client import check_llm_available, get_llm_client
from app.schemas.agent_tools import EquipmentCheckRequest, EquipmentCheckResponse

logger = logging.getLogger(__name__)


class EquipmentAgentService:
    @staticmethod
    def check(payload: EquipmentCheckRequest) -> EquipmentCheckResponse:
        """检查厨具是否满足需求：集合对比由代码完成，建议由 LLM 生成。"""
        owned = {item.strip().lower() for item in payload.equipment_owned if item.strip()}
        required = {item.strip().lower() for item in payload.required_equipment if item.strip()}
        missing = sorted(required - owned)

        if missing:
            suggestion = EquipmentAgentService._generate_suggestion_with_llm(
                owned=list(owned), missing=missing, required=list(required),
            )
            return EquipmentCheckResponse(feasible=False, missing_equipment=missing, suggestion=suggestion)

        suggestion = EquipmentAgentService._generate_suggestion_with_llm(
            owned=list(owned), missing=[], required=list(required),
        )
        return EquipmentCheckResponse(
            feasible=True,
            missing_equipment=[],
            suggestion=suggestion,
        )

    @staticmethod
    def _generate_suggestion_with_llm(
        owned: list[str], missing: list[str], required: list[str],
    ) -> str:
        """调用 LLM 根据厨具匹配情况生成个性化建议。"""
        check_llm_available()

        owned_str = "、".join(owned) if owned else "无"
        missing_str = "、".join(missing) if missing else "无"
        required_str = "、".join(required) if required else "无"

        messages = [
            {
                "role": "system",
                "content": (
                    "你是厨具顾问。根据用户已有厨具和菜谱所需厨具的匹配情况，"
                    "给出实用建议（如替代方案、免烹饪选择等）。用中文回复，简洁实用（100字以内）。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"已有厨具：{owned_str}\n"
                    f"缺少厨具：{missing_str}\n"
                    f"菜谱所需：{required_str}\n\n"
                    f"请根据以上匹配情况给出建议。"
                ),
            },
        ]

        try:
            return get_llm_client().chat(messages, temperature=0.3, max_tokens=200)
        except Exception as exc:
            logger.warning("Equipment suggestion LLM generation failed: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc
