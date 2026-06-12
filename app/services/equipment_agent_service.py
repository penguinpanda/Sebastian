from __future__ import annotations

from app.schemas.agent_tools import EquipmentCheckRequest, EquipmentCheckResponse


class EquipmentAgentService:
    @staticmethod
    def check(payload: EquipmentCheckRequest) -> EquipmentCheckResponse:
        owned = {item.strip().lower() for item in payload.equipment_owned if item.strip()}
        required = {item.strip().lower() for item in payload.required_equipment if item.strip()}
        missing = sorted(required - owned)

        if missing:
            suggestion = "仍可通过替代烹饪方式，或选择免烹饪菜谱完成制作。"
            return EquipmentCheckResponse(feasible=False, missing_equipment=missing, suggestion=suggestion)

        return EquipmentCheckResponse(
            feasible=True,
            missing_equipment=[],
            suggestion="当前厨具已满足该方案制作需求。",
        )
