from __future__ import annotations

from typing import Any

from app.schemas.agent_tools import HealthAnalyzeRequest, HealthAnalyzeResponse
from app.services.health_agent_service import HealthAgentService
from app.orchestration.agent_graphs import run_health_agent


class HealthAgent:
    def __init__(self, service: HealthAgentService | None = None) -> None:
        self._service = service or HealthAgentService()

    def analyze(
        self,
        payload: HealthAnalyzeRequest,
        meal_history: list[dict[str, Any]] | None = None,
        days: int = 7,
    ) -> HealthAnalyzeResponse:
        if meal_history:
            return self._service.analyze_with_history(payload, meal_history, days)
        return self._service.analyze(payload)
