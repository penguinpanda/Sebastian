from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from app.models.task_execution import CeleryTaskExecutionLog


class TaskExecutionLogService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def mark_running(
        self,
        *,
        task_id: str,
        task_name: str,
        trace_id: str | None,
        input_payload: dict | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        record = self._get_or_create(task_id=task_id, task_name=task_name)
        record.task_name = task_name
        record.trace_id = trace_id
        record.status = "running"
        record.input_payload = input_payload
        record.error_detail = None
        record.started_at = now
        record.finished_at = None
        record.duration_ms = None
        self._db.add(record)
        self._db.commit()

    def mark_completed(self, *, task_id: str, output_payload: dict | None) -> None:
        now = datetime.now(timezone.utc)
        record = self._get_or_create(task_id=task_id, task_name="unknown")
        if record.started_at is None:
            record.started_at = now

        record.status = "completed"
        record.output_payload = output_payload
        record.finished_at = now
        started_at = self._ensure_aware(record.started_at)
        record.duration_ms = int((now - started_at).total_seconds() * 1000)
        self._db.add(record)
        self._db.commit()

    def mark_failed(self, *, task_id: str, error_detail: str) -> None:
        now = datetime.now(timezone.utc)
        record = self._get_or_create(task_id=task_id, task_name="unknown")
        if record.started_at is None:
            record.started_at = now

        record.status = "failed"
        record.error_detail = error_detail
        record.finished_at = now
        started_at = self._ensure_aware(record.started_at)
        record.duration_ms = int((now - started_at).total_seconds() * 1000)
        self._db.add(record)
        self._db.commit()

    def get_by_task_id(self, task_id: str) -> CeleryTaskExecutionLog | None:
        return self._db.scalar(select(CeleryTaskExecutionLog).where(CeleryTaskExecutionLog.task_id == task_id))

    def search(
        self,
        *,
        trace_id: str | None,
        status: str | None,
        limit: int,
    ) -> list[CeleryTaskExecutionLog]:
        stmt: Select[tuple[CeleryTaskExecutionLog]] = select(CeleryTaskExecutionLog)
        if trace_id:
            stmt = stmt.where(CeleryTaskExecutionLog.trace_id == trace_id)
        if status:
            stmt = stmt.where(CeleryTaskExecutionLog.status == status)

        stmt = stmt.order_by(desc(CeleryTaskExecutionLog.created_at)).limit(limit)
        return list(self._db.scalars(stmt).all())

    def _get_or_create(self, *, task_id: str, task_name: str) -> CeleryTaskExecutionLog:
        record = self.get_by_task_id(task_id)
        if record:
            return record

        return CeleryTaskExecutionLog(task_id=task_id, task_name=task_name)

    @staticmethod
    def _ensure_aware(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value