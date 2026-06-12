from __future__ import annotations

from app.schemas.agent_tools import SearchAnswerRequest, SearchAnswerResponse
from app.services.search_agent_service import SearchAgentService
from app.orchestration.agent_graphs import run_search_agent


class SearchAgent:
    def __init__(self, service: SearchAgentService | None = None) -> None:
        self._service = service or SearchAgentService()

    def answer(self, payload: SearchAnswerRequest) -> SearchAnswerResponse:
        return run_search_agent(payload, service=self._service)
