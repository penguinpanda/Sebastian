from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.inventory import Inventory, InventoryTransaction


@dataclass(slots=True)
class InventoryRecord:
    """仓储层对外返回的轻量库存记录，隔离 ORM 模型和上层服务。"""

    id: UUID
    user_id: str
    item_type: str
    name: str
    quantity: float
    unit: str
    expire_date: date
    note: str | None
    created_at: datetime
    updated_at: datetime


class InventoryRepository(Protocol):
    """库存仓储协议：测试可注入内存实现，生产可注入 PostgreSQL 实现。"""

    def create(self, user_id: str, name: str, quantity: float, unit: str, expire_date: date, note: str | None = None, item_type: str = "ingredient") -> InventoryRecord:
        ...

    def list_all(self, user_id: str | None = None, item_type: str | None = None) -> list[InventoryRecord]:
        ...

    def get(self, item_id: UUID) -> InventoryRecord:
        ...

    def adjust(self, item_id: UUID, delta: float, note: str | None = None) -> InventoryRecord:
        ...

    def expiring_within(self, days: int, user_id: str | None = None, item_type: str | None = None) -> list[InventoryRecord]:
        ...

    def summary(self, days: int = 7, user_id: str | None = None, item_type: str | None = None) -> tuple[int, int]:
        ...

    def delete(self, item_id: UUID) -> None:
        ...


class InMemoryInventoryRepository:
    """用于单元测试和本地轻量运行的线程安全内存仓储。"""

    def __init__(self) -> None:
        self._items: dict[UUID, InventoryRecord] = {}
        self._lock = Lock()

    def create(self, user_id: str, name: str, quantity: float, unit: str, expire_date: date, note: str | None = None, item_type: str = "ingredient") -> InventoryRecord:
        with self._lock:
            # 同名、同单位、同过期日、同用户、同类型的食材视为同一批次，创建时自动合并数量。
            existing = next(
                (
                    item
                    for item in self._items.values()
                    if item.user_id == user_id
                    and item.item_type == item_type
                    and item.name.strip().lower() == name.strip().lower()
                    and item.unit.strip().lower() == unit.strip().lower()
                    and item.expire_date == expire_date
                ),
                None,
            )
            now = datetime.now(timezone.utc)
            if existing is not None:
                merged = InventoryRecord(
                    id=existing.id,
                    user_id=existing.user_id,
                    item_type=existing.item_type,
                    name=existing.name,
                    quantity=existing.quantity + quantity,
                    unit=existing.unit,
                    expire_date=existing.expire_date,
                    note=note if note is not None else existing.note,
                    created_at=existing.created_at,
                    updated_at=now,
                )
                self._items[merged.id] = merged
                return merged

            record = InventoryRecord(
                id=uuid4(),
                user_id=user_id,
                item_type=item_type,
                name=name,
                quantity=quantity,
                unit=unit,
                expire_date=expire_date,
                note=note,
                created_at=now,
                updated_at=now,
            )
            self._items[record.id] = record
            return record

    def list_all(self, user_id: str | None = None, item_type: str | None = None) -> list[InventoryRecord]:
        with self._lock:
            items = self._items.values()
            if user_id:
                items = [i for i in items if i.user_id == user_id]
            if item_type:
                items = [i for i in items if i.item_type == item_type]
            return sorted(items, key=lambda item: item.created_at, reverse=True)

    def get(self, item_id: UUID) -> InventoryRecord:
        with self._lock:
            record = self._items.get(item_id)
        if record is None:
            raise NotFoundError(f"inventory item {item_id} not found")
        return record

    def adjust(self, item_id: UUID, delta: float, note: str | None = None) -> InventoryRecord:
        with self._lock:
            record = self._items.get(item_id)
            if record is None:
                raise NotFoundError(f"inventory item {item_id} not found")
            new_quantity = record.quantity + delta
            if new_quantity < 0:
                # 负库存会让后续临期统计和菜谱推荐产生误导，所以在仓储层兜底。
                raise ValueError("quantity cannot become negative")
            updated = InventoryRecord(
                id=record.id,
                user_id=record.user_id,
                item_type=record.item_type,
                name=record.name,
                quantity=new_quantity,
                unit=record.unit,
                expire_date=record.expire_date,
                note=note if note is not None else record.note,
                created_at=record.created_at,
                updated_at=datetime.now(timezone.utc),
            )
            self._items[item_id] = updated
            return updated

    def expiring_within(self, days: int, user_id: str | None = None, item_type: str | None = None) -> list[InventoryRecord]:
        today = date.today()
        cutoff = today + timedelta(days=days)
        with self._lock:
            items = self._items.values()
            if user_id:
                items = [i for i in items if i.user_id == user_id]
            if item_type:
                items = [i for i in items if i.item_type == item_type]
            return [item for item in items if today <= item.expire_date <= cutoff]

    def summary(self, days: int = 7, user_id: str | None = None, item_type: str | None = None) -> tuple[int, int]:
        items = self.list_all(user_id=user_id, item_type=item_type)
        expiring = len(self.expiring_within(days, user_id=user_id, item_type=item_type))
        return len(items), expiring

    def delete(self, item_id: UUID) -> None:
        with self._lock:
            if item_id not in self._items:
                raise NotFoundError(f"inventory item {item_id} not found")
            del self._items[item_id]


def build_default_inventory_repository() -> InMemoryInventoryRepository:
    return InMemoryInventoryRepository()


class PostgresInventoryRepository:
    """PostgreSQL 仓储实现，同时维护库存主表和出入库流水。"""

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, user_id: str, name: str, quantity: float, unit: str, expire_date: date, note: str | None = None, item_type: str = "ingredient") -> InventoryRecord:
        normalized_name = name.strip()
        normalized_unit = unit.strip()
        # 数据库实现沿用"同名 + 同单位 + 同过期日 + 同用户 + 同类型合并"的业务规则。
        existing = self._db.scalar(
            select(Inventory)
            .where(Inventory.user_id == user_id)
            .where(Inventory.item_type == item_type)
            .where(func.lower(Inventory.name) == normalized_name.lower())
            .where(func.lower(Inventory.unit) == normalized_unit.lower())
            .where(Inventory.expire_date == expire_date)
            .order_by(Inventory.created_at.desc())
            .limit(1)
        )

        if existing is not None:
            existing.quantity = Decimal(str(float(existing.quantity) + quantity))
            if note is not None:
                existing.note = note

            self._db.add(
                # 每次合并新增也记录一条 IN 流水，便于以后做库存审计。
                InventoryTransaction(
                    inventory_id=existing.id,
                    action="IN",
                    amount=Decimal(str(quantity)),
                    note=note,
                )
            )
            self._db.commit()
            self._db.refresh(existing)
            return self._to_record(existing)

        entity = Inventory(
            user_id=user_id,
            item_type=item_type,
            name=normalized_name,
            quantity=Decimal(str(quantity)),
            unit=normalized_unit,
            expire_date=expire_date,
            note=note,
        )
        self._db.add(entity)
        self._db.flush()

        self._db.add(
            # 新建库存同样生成 IN 流水，保证主表和流水表语义一致。
            InventoryTransaction(
                inventory_id=entity.id,
                action="IN",
                amount=Decimal(str(quantity)),
                note=note,
            )
        )
        self._db.commit()
        self._db.refresh(entity)
        return self._to_record(entity)

    def list_all(self, user_id: str | None = None, item_type: str | None = None) -> list[InventoryRecord]:
        stmt = select(Inventory)
        if user_id:
            stmt = stmt.where(Inventory.user_id == user_id)
        if item_type:
            stmt = stmt.where(Inventory.item_type == item_type)
        entities = self._db.scalars(stmt.order_by(Inventory.created_at.desc())).all()
        return [self._to_record(entity) for entity in entities]

    def get(self, item_id: UUID) -> InventoryRecord:
        entity = self._db.get(Inventory, item_id)
        if entity is None:
            raise NotFoundError(f"inventory item {item_id} not found")
        return self._to_record(entity)

    def adjust(self, item_id: UUID, delta: float, note: str | None = None) -> InventoryRecord:
        entity = self._db.get(Inventory, item_id)
        if entity is None:
            raise NotFoundError(f"inventory item {item_id} not found")

        new_quantity = float(entity.quantity) + delta
        if new_quantity < 0:
            raise ValueError("quantity cannot become negative")

        entity.quantity = Decimal(str(new_quantity))
        if note is not None:
            entity.note = note

        self._db.add(
            # delta 的正负决定流水方向，amount 始终存正数，查询时更直观。
            InventoryTransaction(
                inventory_id=entity.id,
                action="IN" if delta > 0 else "OUT",
                amount=Decimal(str(abs(delta))),
                note=note,
            )
        )
        self._db.commit()
        self._db.refresh(entity)
        return self._to_record(entity)

    def expiring_within(self, days: int, user_id: str | None = None, item_type: str | None = None) -> list[InventoryRecord]:
        today = date.today()
        cutoff = today + timedelta(days=days)
        stmt = (
            select(Inventory)
            .where(Inventory.expire_date >= today)
            .where(Inventory.expire_date <= cutoff)
        )
        if user_id:
            stmt = stmt.where(Inventory.user_id == user_id)
        if item_type:
            stmt = stmt.where(Inventory.item_type == item_type)
        entities = self._db.scalars(stmt.order_by(Inventory.expire_date.asc())).all()
        return [self._to_record(entity) for entity in entities]

    def summary(self, days: int = 7, user_id: str | None = None, item_type: str | None = None) -> tuple[int, int]:
        stmt = select(func.count()).select_from(Inventory)
        if user_id:
            stmt = stmt.where(Inventory.user_id == user_id)
        if item_type:
            stmt = stmt.where(Inventory.item_type == item_type)
        total = self._db.scalar(stmt) or 0
        today = date.today()
        cutoff = today + timedelta(days=days)
        expiring_stmt = (
            select(func.count())
            .select_from(Inventory)
            .where(Inventory.expire_date >= today)
            .where(Inventory.expire_date <= cutoff)
        )
        if user_id:
            expiring_stmt = expiring_stmt.where(Inventory.user_id == user_id)
        if item_type:
            expiring_stmt = expiring_stmt.where(Inventory.item_type == item_type)
        expiring = self._db.scalar(expiring_stmt) or 0
        return int(total), int(expiring)

    def delete(self, item_id: UUID) -> None:
        entity = self._db.get(Inventory, item_id)
        if entity is None:
            raise NotFoundError(f"inventory item {item_id} not found")
        self._db.delete(entity)
        self._db.commit()

    @staticmethod
    def _to_record(entity: Inventory) -> InventoryRecord:
        return InventoryRecord(
            id=entity.id,
            user_id=entity.user_id,
            item_type=entity.item_type,
            name=entity.name,
            quantity=float(entity.quantity),
            unit=entity.unit,
            expire_date=entity.expire_date,
            note=entity.note,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
