"""Meal confirmation — 用户确认制作菜谱 → 扣库存 → 写饮食历史。"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session, get_inventory_service
from app.models.meal import MealHistory
from app.models.recipe import Recipe
from app.schemas.agent_tools import RecipeRecommendResponse
from app.schemas.inventory import InventoryAdjust
from app.services.inventory_service import InventoryService

router = APIRouter(prefix="/meals")


class MealConfirmRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    recipe: RecipeRecommendResponse


class MealConfirmResponse(BaseModel):
    meal_id: str
    status: str
    deducted: list[dict]
    missing: list[dict]
    errors: list[str]


@router.post("/confirm", response_model=MealConfirmResponse, status_code=status.HTTP_201_CREATED)
def confirm_meal(
    payload: MealConfirmRequest,
    request: Request,
    db: Session = Depends(get_db_session),
    inventory_service: InventoryService = Depends(get_inventory_service),
) -> MealConfirmResponse:
    """用户确认制作菜谱：
    1. 按菜谱配料扣减库存
    2. 写入 MealHistory 饮食记录
    """
    request.state.user_id = payload.user_id
    request.state.action = "confirm_meal"

    # 1. 批量扣减库存（按用户隔离）
    ingredients = payload.recipe.ingredients or []
    batch_result = inventory_service.batch_adjust_by_ingredients(ingredients, user_id=payload.user_id)

    # 2. 写入饮食历史（含扣减明细，用于回退）
    meal = MealHistory(
        id=uuid4(),
        user_id=payload.user_id,
        meal_date=date.today(),
        recipe_title=payload.recipe.title,
        estimated_calories=payload.recipe.estimated_calories,
        recipe_data=payload.recipe.model_dump(),
        deducted_detail=batch_result.deducted if batch_result.deducted else None,
        confirmed_at=datetime.now(timezone.utc),
    )
    db.add(meal)

    # 3. 自动入库菜谱库（去重）
    content = f"{payload.recipe.title}|{'|'.join(sorted(i.name for i in payload.recipe.ingredients))}"
    recipe_hash = hashlib.md5(content.encode()).hexdigest()

    existing_recipe = db.execute(
        select(Recipe).where(Recipe.content_hash == recipe_hash)
    ).scalars().first()

    if existing_recipe:
        existing_recipe.times_made += 1
        existing_recipe.updated_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    else:
        db.add(Recipe(
            id=uuid4(),
            title=payload.recipe.title,
            user_id=payload.user_id,
            estimated_calories=payload.recipe.estimated_calories,
            ingredients=[i.model_dump() for i in payload.recipe.ingredients],
            steps=list(payload.recipe.steps),
            required_equipment=list(payload.recipe.required_equipment),
            recipe_data=payload.recipe.model_dump(),
            content_hash=recipe_hash,
        ))

    db.commit()

    return MealConfirmResponse(
        meal_id=str(meal.id),
        status="confirmed",
        deducted=batch_result.deducted,
        missing=batch_result.missing,
        errors=batch_result.errors,
    )


class MealRollbackResponse(BaseModel):
    meal_id: str
    status: str
    restored: list[dict]
    errors: list[str]


@router.post("/{meal_id}/rollback", response_model=MealRollbackResponse)
def rollback_meal(
    meal_id: str,
    request: Request,
    db: Session = Depends(get_db_session),
    inventory_service: InventoryService = Depends(get_inventory_service),
) -> MealRollbackResponse:
    """回退已确认的餐食：将扣减的库存恢复。
    
    只能回退未回退过的记录，回退后标记 rolled_back_at。
    """
    from uuid import UUID as _UUID

    try:
        meal_uuid = _UUID(meal_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的 meal_id")

    meal = db.get(MealHistory, meal_uuid)
    if meal is None:
        raise HTTPException(status_code=404, detail="未找到该饮食记录")

    if meal.rolled_back_at is not None:
        raise HTTPException(status_code=409, detail="该餐食已回退，不可重复回退")

    request.state.user_id = meal.user_id
    request.state.action = "rollback_meal"

    deducted = meal.deducted_detail or []
    restored: list[dict] = []
    errors: list[str] = []

    for entry in deducted:
        inv_id_str = entry.get("inventory_id")
        amount = entry.get("amount", 0)
        if not inv_id_str or amount <= 0:
            continue
        try:
            inv_uuid = _UUID(inv_id_str)
            inventory_service.adjust_item(
                inv_uuid,
                InventoryAdjust(delta=float(amount), note=f"回退餐食: {meal.recipe_title}"),
            )
            restored.append(entry)
        except Exception as exc:
            errors.append(f"{entry.get('name', '?')}: {exc}")

    if restored:
        meal.rolled_back_at = datetime.now(timezone.utc)
        db.commit()

    return MealRollbackResponse(
        meal_id=meal_id,
        status="rolled_back" if restored else "partial",
        restored=restored,
        errors=errors,
    )


class MealHistoryResponse(BaseModel):
    meals: list[dict]
    count: int


@router.get("/history", response_model=MealHistoryResponse)
def get_meal_history(
    user_id: str = Query(min_length=1, max_length=64),
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db_session),
) -> MealHistoryResponse:
    """查询用户最近 N 天的饮食历史，供 HealthAgent 和前端使用。"""
    cutoff = date.today() - __import__("datetime").timedelta(days=days)
    stmt = (
        select(MealHistory)
        .where(MealHistory.user_id == user_id, MealHistory.meal_date >= cutoff)
        .order_by(MealHistory.meal_date.desc(), MealHistory.confirmed_at.desc())
    )
    rows = db.execute(stmt).scalars().all()
    return MealHistoryResponse(
        meals=[{"id": str(m.id), "title": m.recipe_title, "calories": m.estimated_calories,
                "meal_date": str(m.meal_date), "confirmed_at": m.confirmed_at.isoformat()} for m in rows],
        count=len(rows),
    )
