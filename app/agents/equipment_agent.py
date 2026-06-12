from __future__ import annotations

from app.schemas.agent_tools import EquipmentCheckRequest, EquipmentCheckResponse
from app.services.equipment_agent_service import EquipmentAgentService
from app.orchestration.agent_graphs import run_equipment_agent


class EquipmentAgent:
    def __init__(self, service: EquipmentAgentService | None = None) -> None:
        self._service = service or EquipmentAgentService()

    def check(self, payload: EquipmentCheckRequest) -> EquipmentCheckResponse:
        return run_equipment_agent(payload, service=self._service)
