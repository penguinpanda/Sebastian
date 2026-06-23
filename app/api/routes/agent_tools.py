from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.agents.equipment_agent import EquipmentAgent
from app.agents.health_agent import HealthAgent
from app.agents.recipe_agent import RecipeAgent
from app.agents.search_agent import SearchAgent
from app.models.meal import MealHistory
from app.models.user_profile import UserProfile
from app.repositories.inventory import PostgresInventoryRepository
from app.schemas.agent_tools import (
    EquipmentCheckRequest,
    EquipmentCheckResponse,
    HealthAnalyzeRequest,
    HealthAnalyzeResponse,
    InventoryOnlyRecipeRequest,
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


def get_health_agent(db: Session = Depends(get_db_session)) -> HealthAgent:
    agent = HealthAgent()
    # 预取用户饮食历史注入 Agent，使分析结果包含近期饮食洞察
    agent._db = db
    return agent


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


@router.post("/recipe/recommend-from-inventory", response_model=RecipeRecommendResponse)
def recipe_recommend_from_inventory(
    payload: InventoryOnlyRecipeRequest,
    request: Request,
    agent: RecipeAgent = Depends(get_recipe_agent),
) -> RecipeRecommendResponse:
    """仅使用库存材料生成菜谱：获取真实库存，将库存约束传递给 LLM 生成菜谱。

    库存为空返回 400；LLM 不可用返回 503。不允许使用模板或模拟结果。
    """
    request.state.user_id = payload.user_id
    request.state.action = "recipe_recommend_from_inventory"
    return agent.recommend_from_inventory(payload)


@router.post("/health/analyze", response_model=HealthAnalyzeResponse)
def health_analyze(
    payload: HealthAnalyzeRequest,
    request: Request,
    agent: HealthAgent = Depends(get_health_agent),
) -> HealthAnalyzeResponse:
    request.state.user_id = payload.user_id
    request.state.action = "health_analyze"

    db = getattr(agent, '_db', None)
    meal_history: list[dict] = []
    user_profile: dict | None = None

    if db:
        # 查询用户健康档案
        profile = db.execute(
            select(UserProfile).where(UserProfile.user_id == payload.user_id)
        ).scalars().first()
        if profile:
            user_profile = {
                "age": profile.age,
                "gender": profile.gender,
                "height_cm": profile.height_cm,
                "weight_kg": profile.weight_kg,
                "activity_level": profile.activity_level,
                "health_goal": profile.health_goal,
            }
            # 如果档案中有身高体重，优先使用
            if profile.height_cm and payload.height_cm == 0:
                payload.height_cm = profile.height_cm
            if profile.weight_kg and payload.weight_kg == 0:
                payload.weight_kg = profile.weight_kg

        # 查询饮食历史
        cutoff = date.today() - timedelta(days=7)
        stmt = select(MealHistory).where(
            MealHistory.user_id == payload.user_id,
            MealHistory.meal_date >= cutoff,
        ).order_by(MealHistory.meal_date.desc())
        rows = db.execute(stmt).scalars().all()
        meal_history = [
            {"title": m.recipe_title, "calories": m.estimated_calories,
             "meal_date": str(m.meal_date), "confirmed_at": m.confirmed_at.isoformat()}
            for m in rows
        ]

    return agent.analyze(payload, meal_history=meal_history, days=7)


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
