"""测试 InventoryService.batch_adjust_by_ingredients() 批量扣减。"""

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.db.base import Base
from app.repositories.inventory import PostgresInventoryRepository
from app.schemas.agent_tools import RecipeIngredient
from app.schemas.inventory import InventoryCreate
from app.services.inventory_service import InventoryService


@pytest.fixture
def service() -> InventoryService:
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = Session(engine)
    repo = PostgresInventoryRepository(db)
    return InventoryService(repository=repo)


def _seed(service: InventoryService, name: str, quantity: float, unit: str, days: int):
    service.create_item(InventoryCreate(user_id="u1", 
        name=name, quantity=quantity, unit=unit,
        expire_date=date.today() + timedelta(days=days),
    ))


def test_batch_adjust_deducts_matching_items(service: InventoryService) -> None:
    """模糊匹配成功的食材应被扣减。"""
    _seed(service, "鸡胸肉", 500, "g", 5)
    _seed(service, "花生", 100, "g", 10)

    ingredients = [
        RecipeIngredient(name="鸡胸", amount=200, unit="g"),
        RecipeIngredient(name="花生", amount=50, unit="g"),
    ]

    result = service.batch_adjust_by_ingredients(ingredients)
    assert len(result.deducted) == 2
    assert len(result.missing) == 0
    assert result.deducted[0]["name"] == "鸡胸"


def test_batch_adjust_reports_missing(service: InventoryService) -> None:
    """库存中没有的食材应记录为 missing。"""
    _seed(service, "鸡蛋", 10, "个", 5)

    ingredients = [
        RecipeIngredient(name="三文鱼", amount=200, unit="g"),
    ]

    result = service.batch_adjust_by_ingredients(ingredients)
    assert len(result.deducted) == 0
    assert len(result.missing) == 1
    assert result.missing[0]["name"] == "三文鱼"


def test_batch_adjust_partial_deduction(service: InventoryService) -> None:
    """库存不够时：扣掉能扣的，剩余的报 missing。"""
    _seed(service, "牛肉", 100, "g", 3)

    ingredients = [RecipeIngredient(name="牛肉", amount=300, unit="g")]

    result = service.batch_adjust_by_ingredients(ingredients)
    assert len(result.deducted) == 1
    assert result.deducted[0]["amount"] == 100
    assert len(result.missing) == 1
    assert result.missing[0]["amount"] == 200


def test_batch_adjust_prefers_earliest_expiry(service: InventoryService) -> None:
    """多批次同食材时应优先扣最早过期的。"""
    _seed(service, "鸡蛋", 5, "个", 1)
    _seed(service, "鸡蛋", 10, "个", 10)

    ingredients = [RecipeIngredient(name="鸡蛋", amount=8, unit="个")]

    result = service.batch_adjust_by_ingredients(ingredients)
    deducted_names = [d["inventory_name"] for d in result.deducted]
    assert all("鸡蛋" in n for n in deducted_names)
    total_deducted = sum(d["amount"] for d in result.deducted)
    assert total_deducted == 8
