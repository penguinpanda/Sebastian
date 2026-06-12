from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.agents.equipment_agent import EquipmentAgent
from app.agents.health_agent import HealthAgent
from app.agents.recipe_agent import RecipeAgent
from app.agents.search_agent import SearchAgent
from app.repositories.inventory import PostgresInventoryRepository
from app.schemas.agent_tools import (
    EquipmentCheckRequest,
    EquipmentCheckResponse,
    HealthAnalyzeRequest,
    HealthAnalyzeResponse,
    RecipeRecommendRequest,
    RecipeRecommendResponse,
    SearchAnswerRequest,
    SearchAnswerResponse,
)
from app.services.inventory_service import InventoryService
from app.services.recipe_agent_service import RecipeAgentService

router = APIRouter(prefix="/agents")


def get_recipe_agent(db: Session = Depends(get_db_session)) -> RecipeAgent:
    inventory_service = InventoryService(repository=PostgresInventoryRepository(db))
    return RecipeAgent(service=RecipeAgentService(inventory_service=inventory_service))


def get_health_agent() -> HealthAgent:
    return HealthAgent()


def get_equipment_agent() -> EquipmentAgent:
    return EquipmentAgent()


def get_search_agent() -> SearchAgent:
    return SearchAgent()


@router.post("/recipe/recommend", response_model=RecipeRecommendResponse)
def recipe_recommend(
    payload: RecipeRecommendRequest,
    request: Request,
    agent: RecipeAgent = Depends(get_recipe_agent),
) -> RecipeRecommendResponse:
    request.state.user_id = payload.user_id
    request.state.action = "recipe_recommend"
    return agent.recommend(payload)


@router.post("/health/analyze", response_model=HealthAnalyzeResponse)
def health_analyze(
    payload: HealthAnalyzeRequest,
    request: Request,
    agent: HealthAgent = Depends(get_health_agent),
) -> HealthAnalyzeResponse:
    request.state.user_id = payload.user_id
    request.state.action = "health_analyze"
    return agent.analyze(payload)


@router.post("/equipment/check", response_model=EquipmentCheckResponse)
def equipment_check(
    payload: EquipmentCheckRequest,
    request: Request,
    agent: EquipmentAgent = Depends(get_equipment_agent),
) -> EquipmentCheckResponse:
    request.state.action = "equipment_check"
    return agent.check(payload)


@router.post("/search/answer", response_model=SearchAnswerResponse)
def search_answer(
    payload: SearchAnswerRequest,
    request: Request,
    agent: SearchAgent = Depends(get_search_agent),
) -> SearchAnswerResponse:
    request.state.user_id = payload.user_id
    request.state.action = "search_answer"
    return agent.answer(payload)
