from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.services.task_execution_log_service import TaskExecutionLogService


def test_task_execution_log_service_persists_and_searches() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
      service = TaskExecutionLogService(db)
      service.mark_running(
          task_id="celery-1",
          task_name="app.tasks.inventory_tasks.scan_expiring_inventory",
          trace_id="trace-1",
          input_payload={"days": 3},
      )
      service.mark_completed(
          task_id="celery-1",
          output_payload={"status": "ok", "count": 1},
      )

      found = service.get_by_task_id("celery-1")
      assert found is not None
      assert found.trace_id == "trace-1"
      assert found.status == "completed"
      assert found.duration_ms is not None

      by_trace = service.search(trace_id="trace-1", status=None, limit=10)
      assert len(by_trace) == 1
      assert by_trace[0].task_id == "celery-1"


def test_task_execution_log_service_mark_failed() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
      service = TaskExecutionLogService(db)
      service.mark_running(
          task_id="celery-2",
          task_name="app.tasks.inventory_tasks.scan_expiring_inventory",
          trace_id="trace-2",
          input_payload={"days": 3},
      )
      service.mark_failed(task_id="celery-2", error_detail="boom")

      found = service.get_by_task_id("celery-2")
      assert found is not None
      assert found.status == "failed"
      assert found.error_detail == "boom"
