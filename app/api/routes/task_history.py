from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db_session
from app.schemas.task_execution import TaskExecutionLogListResponse, TaskExecutionLogRead
from app.services.task_execution_log_service import TaskExecutionLogService

router = APIRouter(prefix="/tasks")


def get_task_execution_log_service(db: Session = Depends(get_db_session)) -> TaskExecutionLogService:
    return TaskExecutionLogService(db)


@router.get("/history/{task_id}", response_model=TaskExecutionLogRead)
def get_task_history_by_task_id(
    task_id: str,
    service: TaskExecutionLogService = Depends(get_task_execution_log_service),
) -> TaskExecutionLogRead:
    record = service.get_by_task_id(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Task execution history not found")

    return TaskExecutionLogRead.model_validate(record)


@router.get("/history", response_model=TaskExecutionLogListResponse)
def search_task_history(
    trace_id: str | None = Query(default=None, min_length=1, max_length=64),
    status: str | None = Query(default=None, min_length=1, max_length=20),
    limit: int = Query(default=20, ge=1, le=100),
    service: TaskExecutionLogService = Depends(get_task_execution_log_service),
) -> TaskExecutionLogListResponse:
    records = service.search(trace_id=trace_id, status=status, limit=limit)
    return TaskExecutionLogListResponse(
        items=[TaskExecutionLogRead.model_validate(item) for item in records],
        total=len(records),
    )