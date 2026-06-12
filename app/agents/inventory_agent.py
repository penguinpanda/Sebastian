from uuid import UUID

from app.schemas.inventory import InventoryAdjust, InventoryCreate, InventoryRead
from app.services.inventory_service import InventoryService


class InventoryAgent:
    def __init__(self, service: InventoryService | None = None) -> None:
        self._service = service or InventoryService()

    def create_item(self, payload: InventoryCreate) -> InventoryRead:
        return self._service.create_item(payload)

    def adjust_item(self, item_id: UUID, payload: InventoryAdjust) -> InventoryRead:
        return self._service.adjust_item(item_id, payload)
