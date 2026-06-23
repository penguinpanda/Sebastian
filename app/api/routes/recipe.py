"""Recipe library — 菜谱库检索 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.models.recipe import Recipe

router = APIRouter(prefix="/recipes")


class RecipeLibraryItem(BaseModel):
    id: str
    title: str
    estimated_calories: int
    ingredients: list[dict]
    steps: list[str]
    times_made: int
    created_at: str


class RecipeLibraryResponse(BaseModel):
    recipes: list[RecipeLibraryItem]
    count: int


def _to_item(r: Recipe) -> RecipeLibraryItem:
    return RecipeLibraryItem(
        id=str(r.id),
        title=r.title,
        estimated_calories=r.estimated_calories,
        ingredients=r.ingredients or [],
        steps=r.steps or [],
        times_made=r.times_made,
        created_at=r.created_at.isoformat(),
    )


@router.get("", response_model=RecipeLibraryResponse)
def list_recipes(
    user_id: str = Query(min_length=1, max_length=64),
    query: str = Query(default="", max_length=200),
    sort: str = Query(default="times_made", pattern="^(times_made|calories|recent)$"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db_session),
) -> RecipeLibraryResponse:
    """搜索菜谱库：支持标题模糊搜索，排序方式可选制作次数/热量/最近。"""
    stmt = select(Recipe).where(Recipe.user_id == user_id)

    if query.strip():
        stmt = stmt.where(Recipe.title.ilike(f"%{query.strip()}%"))

    # 排序
    if sort == "calories":
        stmt = stmt.order_by(Recipe.estimated_calories.asc())
    elif sort == "recent":
        stmt = stmt.order_by(Recipe.created_at.desc())
    else:
        stmt = stmt.order_by(Recipe.times_made.desc())

    stmt = stmt.limit(limit)
    rows = db.execute(stmt).scalars().all()

    return RecipeLibraryResponse(
        recipes=[_to_item(r) for r in rows],
        count=len(rows),
    )


@router.get("/top", response_model=RecipeLibraryResponse)
def top_recipes(
    user_id: str = Query(min_length=1, max_length=64),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db_session),
) -> RecipeLibraryResponse:
    """返回用户最常制作的菜谱 Top N，供首页快捷推荐。"""
    stmt = (
        select(Recipe)
        .where(Recipe.user_id == user_id)
        .order_by(Recipe.times_made.desc(), Recipe.created_at.desc())
        .limit(limit)
    )
    rows = db.execute(stmt).scalars().all()
    return RecipeLibraryResponse(
        recipes=[_to_item(r) for r in rows],
        count=len(rows),
    )
