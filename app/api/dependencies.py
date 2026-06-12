from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.inventory import PostgresInventoryRepository
from app.services.inventory_service import InventoryService


def get_inventory_service(db: Session = Depends(get_db_session)) -> InventoryService:
    return InventoryService(repository=PostgresInventoryRepository(db))

