from datetime import date, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.inventory import InventoryTransaction
from app.repositories.inventory import PostgresInventoryRepository


def test_postgres_repository_create_and_adjust_writes_transactions() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        repository = PostgresInventoryRepository(db)
        item = repository.create(
            name="Egg",
            quantity=10,
            unit="pcs",
            expire_date=date.today() + timedelta(days=5),
            note="initial stock",
        )

        adjusted = repository.adjust(item.id, -3, "used for dinner")
        assert adjusted.quantity == 7

        transactions = db.scalars(select(InventoryTransaction).where(InventoryTransaction.inventory_id == item.id)).all()
        assert len(transactions) == 2
        assert {t.action for t in transactions} == {"IN", "OUT"}


def test_postgres_repository_adjust_negative_result_raises() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        repository = PostgresInventoryRepository(db)
        item = repository.create(
            name="Butter",
            quantity=1,
            unit="block",
            expire_date=date.today() + timedelta(days=3),
        )

        try:
            repository.adjust(item.id, -2)
            assert False, "expected ValueError"
        except ValueError as exc:
            assert str(exc) == "quantity cannot become negative"


def test_postgres_repository_create_merges_same_item() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        repository = PostgresInventoryRepository(db)
        expire_date = date.today() + timedelta(days=4)
        first = repository.create(name="Egg", quantity=2, unit="pcs", expire_date=expire_date)
        second = repository.create(name="egg", quantity=3, unit="PCS", expire_date=expire_date)

        assert first.id == second.id
        assert second.quantity == 5


def test_postgres_repository_delete_item() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        repository = PostgresInventoryRepository(db)
        item = repository.create(
            name="Cheese",
            quantity=1,
            unit="pack",
            expire_date=date.today() + timedelta(days=5),
        )

        repository.delete(item.id)

        try:
            repository.get(item.id)
            assert False, "expected NotFoundError"
        except Exception as exc:
            assert "not found" in str(exc)
