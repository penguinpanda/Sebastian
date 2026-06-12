from __future__ import annotations

from datetime import date
from uuid import UUID

from app.core.errors import ValidationError
from app.repositories.inventory import InventoryRecord, InventoryRepository, build_default_inventory_repository
from app.schemas.inventory import ExpiringInventoryItem, InventoryAdjust, InventoryCreate, InventoryRead, InventorySummary


class InventoryService:
    """库存业务服务：承接路由输入，屏蔽底层仓储实现差异。"""

    def __init__(self, repository: InventoryRepository | None = None) -> None:
        self._repository = repository or build_default_inventory_repository()

    def create_item(self, payload: InventoryCreate) -> InventoryRead:
        """创建库存前做轻量归一化，避免同一食材因空格被视为不同记录。"""
        record = self._repository.create(
            name=payload.name.strip(),
            quantity=payload.quantity,
            unit=payload.unit.strip(),
            expire_date=payload.expire_date,
            note=payload.note.strip() if payload.note else None,
        )
        return self._to_read(record)

    def list_items(self) -> list[InventoryRead]:
        return [self._to_read(record) for record in self._repository.list_all()]

    def get_item(self, item_id: UUID) -> InventoryRead:
        return self._to_read(self._repository.get(item_id))

    def adjust_item(self, item_id: UUID, payload: InventoryAdjust) -> InventoryRead:
        """库存调整只接受非零增量；是否会变成负数由仓储层按当前数量校验。"""
        if payload.delta == 0:
            raise ValidationError("delta must not be zero")
        try:
            record = self._repository.adjust(item_id, payload.delta, payload.note)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._to_read(record)

    def expiring_items(self, days: int) -> list[ExpiringInventoryItem]:
        """把仓储记录转换成前端更关心的 days_left 展示字段。"""
        today = date.today()
        items = self._repository.expiring_within(days)
        return [
            ExpiringInventoryItem(
                id=record.id,
                name=record.name,
                quantity=record.quantity,
                unit=record.unit,
                expire_date=record.expire_date,
                days_left=(record.expire_date - today).days,
            )
            for record in items
        ]

    def summary(self, days: int = 7) -> InventorySummary:
        total_items, expiring_soon = self._repository.summary(days)
        return InventorySummary(total_items=total_items, expiring_soon=expiring_soon)

    def delete_item(self, item_id: UUID) -> None:
        self._repository.delete(item_id)

    @staticmethod
    def _to_read(record: InventoryRecord) -> InventoryRead:
        """统一 DTO 转换出口，避免路由层依赖仓储内部数据结构。"""
        return InventoryRead(
            id=record.id,
            name=record.name,
            quantity=record.quantity,
            unit=record.unit,
            expire_date=record.expire_date,
            note=record.note,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )
