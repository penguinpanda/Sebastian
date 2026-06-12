from __future__ import annotations

from app.schemas.agent_tools import HealthAnalyzeRequest, HealthAnalyzeResponse
from app.services.health_agent_service import HealthAgentService
from app.orchestration.agent_graphs import run_health_agent


class HealthAgent:
    def __init__(self, service: HealthAgentService | None = None) -> None:
        self._service = service or HealthAgentService()

    def analyze(self, payload: HealthAnalyzeRequest) -> HealthAnalyzeResponse:
        return run_health_agent(payload, service=self._service)
