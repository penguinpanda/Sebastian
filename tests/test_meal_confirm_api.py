"""测试 POST /api/meals/confirm 确认制作接口。"""

import os
import tempfile
from datetime import date, timedelta

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.api.dependencies import get_db_session, get_inventory_service
from app.db.base import Base
from app.main import app
from app.models.meal import MealHistory
from app.models.recipe import Recipe
from app.repositories.inventory import PostgresInventoryRepository
from app.schemas.inventory import InventoryCreate
from app.services.inventory_service import InventoryService


@pytest.fixture
def engine():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    eng = create_engine(f"sqlite+pysqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()
    try: os.unlink(path)
    except OSError: pass


def make_recipe(**kw) -> dict:
    d = {"title":"宫保鸡丁","rationale":"测试","estimated_calories":600,
         "ingredients":[{"name":"鸡胸肉","amount":200,"unit":"g"},{"name":"花生","amount":50,"unit":"g"}],
         "steps":["炒"],"required_equipment":["pan"],"missing_ingredients":[],"feasible":True,"missing_equipment":[]}
    d.update(kw); return d


def seed_stock(engine):
    svc = InventoryService(repository=PostgresInventoryRepository(Session(engine)))
    svc.create_item(InventoryCreate(user_id="u1", name="鸡胸肉", quantity=500, unit="g", expire_date=date.today() + timedelta(5)))
    svc.create_item(InventoryCreate(user_id="u1", name="花生", quantity=100, unit="g", expire_date=date.today() + timedelta(10)))


@pytest.mark.asyncio
async def test_confirm_meal_deducts_and_writes(engine) -> None:
    seed_stock(engine)
    app.dependency_overrides[get_db_session] = lambda: Session(engine)
    app.dependency_overrides[get_inventory_service] = lambda: InventoryService(
        repository=PostgresInventoryRepository(Session(engine)))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        resp = await c.post("/api/meals/confirm", json={"user_id": "u1", "recipe": make_recipe()})
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "confirmed"
    assert len(data["deducted"]) == 2

    db = Session(engine)
    meals = db.scalars(select(MealHistory).where(MealHistory.user_id == "u1")).all()
    assert len(meals) == 1
    assert meals[0].recipe_title == "宫保鸡丁"
    recipes = db.scalars(select(Recipe).where(Recipe.user_id == "u1")).all()
    assert len(recipes) == 1
    assert recipes[0].times_made == 1
    db.close()
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_confirm_meal_times_made_increments(engine) -> None:
    seed_stock(engine)
    app.dependency_overrides[get_db_session] = lambda: Session(engine)
    app.dependency_overrides[get_inventory_service] = lambda: InventoryService(
        repository=PostgresInventoryRepository(Session(engine)))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        await c.post("/api/meals/confirm", json={"user_id": "u1", "recipe": make_recipe()})
        await c.post("/api/meals/confirm", json={"user_id": "u1", "recipe": make_recipe()})

    db = Session(engine)
    recipes = db.scalars(select(Recipe).where(Recipe.user_id == "u1")).all()
    assert len(recipes) == 1
    assert recipes[0].times_made == 2
    db.close()
    app.dependency_overrides.clear()
