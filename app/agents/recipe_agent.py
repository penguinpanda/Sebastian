from __future__ import annotations

from app.schemas.agent_tools import RecipeRecommendRequest, RecipeRecommendResponse
from app.services.recipe_agent_service import RecipeAgentService
from app.orchestration.agent_graphs import run_recipe_agent


class RecipeAgent:
    def __init__(self, service: RecipeAgentService | None = None) -> None:
        self._service = service or RecipeAgentService()

    def recommend(self, payload: RecipeRecommendRequest) -> RecipeRecommendResponse:
        return run_recipe_agent(payload, recipe_service=self._service)
