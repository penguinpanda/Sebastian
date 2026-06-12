from __future__ import annotations

import logging
from uuid import uuid4

from celery import current_task

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.repositories.inventory import PostgresInventoryRepository
from app.services.agent_task_queue import enqueue_agent_task
from app.services.inventory_service import InventoryService
from app.services.task_execution_log_service import TaskExecutionLogService
from app.workers.celery_app import celery_app


logger = logging.getLogger(__name__)
settings = get_settings()


@celery_app.task(
    name="app.tasks.inventory_tasks.scan_expiring_inventory",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": settings.celery_scan_max_retries},
)
def scan_expiring_inventory(days: int = 3, trace_id: str | None = None) -> dict:
    if days < 1 or days > 365:
        raise ValueError("days must be between 1 and 365")

    celery_task_id = _resolve_celery_task_id()
    session_factory = get_session_factory()
    db = session_factory()
    execution_log_service = TaskExecutionLogService(db)
    try:
        _safe_mark_running(
            execution_log_service,
            task_id=celery_task_id,
            task_name="app.tasks.inventory_tasks.scan_expiring_inventory",
            trace_id=trace_id,
            input_payload={"days": days},
        )

        service = InventoryService(repository=PostgresInventoryRepository(db))
        items = service.expiring_items(days)

        alerts = [
            {
                "id": str(item.id),
                "name": item.name,
                "expire_date": item.expire_date.isoformat(),
                "days_left": item.days_left,
            }
            for item in items
        ]

        # Reuse Redis queue as lightweight reminder queue in MVP.
        for alert in alerts:
            enqueue_agent_task(
                task_id=f"inventory-expiring-{alert['id']}",
                user_id="system",
                message=f"{alert['name']} expires in {alert['days_left']} day(s)",
                trace_id=trace_id,
            )

        output_payload = {"status": "ok", "days": days, "count": len(alerts), "alerts": alerts, "trace_id": trace_id}
        _safe_mark_completed(execution_log_service, task_id=celery_task_id, output_payload=output_payload)
        return output_payload
    except Exception as exc:
        failure_message = f"inventory scan failed for days={days}: {exc}"
        logger.exception("Inventory expiring scan failed: %s", failure_message)
        _safe_mark_failed(execution_log_service, task_id=celery_task_id, error_detail=failure_message)
        enqueue_agent_task(
            task_id="inventory-expiring-scan-failure",
            user_id="system",
            message=failure_message,
            trace_id=trace_id,
        )
        raise
    finally:
        db.close()


def _resolve_celery_task_id() -> str:
    request = getattr(current_task, "request", None)
    task_id = getattr(request, "id", None)
    if task_id:
        return str(task_id)
    return f"local-{uuid4()}"


def _safe_mark_running(service: TaskExecutionLogService, **kwargs) -> None:
    try:
        service.mark_running(**kwargs)
    except Exception as exc:
        logger.warning("failed to persist running task execution log: %s", exc)


def _safe_mark_completed(service: TaskExecutionLogService, **kwargs) -> None:
    try:
        service.mark_completed(**kwargs)
    except Exception as exc:
        logger.warning("failed to persist completed task execution log: %s", exc)


def _safe_mark_failed(service: TaskExecutionLogService, **kwargs) -> None:
    try:
        service.mark_failed(**kwargs)
    except Exception as exc:
        logger.warning("failed to persist failed task execution log: %s", exc)
