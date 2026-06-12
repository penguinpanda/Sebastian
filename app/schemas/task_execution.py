from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskExecutionLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    task_name: str
    trace_id: str | None = None
    status: str
    input_payload: dict | None = None
    output_payload: dict | None = None
    error_detail: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


class TaskExecutionLogListResponse(BaseModel):
    items: list[TaskExecutionLogRead] = Field(default_factory=list)
    total: int