from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies import get_inventory_service
from app.core.errors import NotFoundError, ValidationError
from app.schemas.inventory import ExpiringInventoryItem, InventoryAdjust, InventoryCreate, InventoryRead, InventorySummary
from app.services.inventory_service import InventoryService
from app.tasks.inventory_tasks import scan_expiring_inventory


router = APIRouter(prefix="/inventory")


@router.post("/tasks/scan-expiring")
def trigger_scan_expiring_task(request: Request, days: int = Query(default=3, ge=1, le=30)) -> dict[str, str | int | None]:
    """触发异步临期扫描任务，HTTP 请求只负责入队，不等待 Celery 执行完成。"""
    request.state.action = "scan_expiring_inventory"
    trace_id = getattr(request.state, "trace_id", None)
    result = scan_expiring_inventory.delay(days, trace_id)
    return {"status": "queued", "task_id": str(result.id), "days": days, "trace_id": trace_id}


@router.post("", response_model=InventoryRead, status_code=status.HTTP_201_CREATED)
def create_inventory_item(
    payload: InventoryCreate,
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryRead:
    return service.create_item(payload)


@router.get("", response_model=list[InventoryRead])
def list_inventory_items(
    user_id: str = Query(default="default", min_length=1, max_length=64),
    service: InventoryService = Depends(get_inventory_service),
) -> list[InventoryRead]:
    return service.list_items(user_id=user_id)


@router.get("/summary", response_model=InventorySummary)
def get_inventory_summary(
    days: int = Query(default=7, ge=1, le=365),
    user_id: str = Query(default="default", min_length=1, max_length=64),
    service: InventoryService = Depends(get_inventory_service),
) -> InventorySummary:
    return service.summary(days, user_id=user_id)


@router.get("/{item_id}", response_model=InventoryRead)
def get_inventory_item(
    item_id: UUID,
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryRead:
    try:
        return service.get_item(item_id)
    except NotFoundError as exc:
        # 服务层抛业务异常，路由层负责转换成稳定的 HTTP 语义。
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.patch("/{item_id}/adjust", response_model=InventoryRead)
def adjust_inventory_item(
    item_id: UUID,
    payload: InventoryAdjust,
    service: InventoryService = Depends(get_inventory_service),
) -> InventoryRead:
    try:
        return service.adjust_item(item_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_inventory_item(
    item_id: UUID,
    service: InventoryService = Depends(get_inventory_service),
) -> None:
    try:
        service.delete_item(item_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/alerts/expiring", response_model=list[ExpiringInventoryItem])
def list_expiring_items(
    days: int = Query(default=7, ge=1, le=365),
    user_id: str = Query(default="default", min_length=1, max_length=64),
    service: InventoryService = Depends(get_inventory_service),
) -> list[ExpiringInventoryItem]:
    """返回未来 days 天内到期的库存，供首页提醒和定时任务复用。"""
    return service.expiring_items(days, user_id=user_id)
