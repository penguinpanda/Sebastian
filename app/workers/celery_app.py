from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

# Celery worker 与 FastAPI 共用同一份 settings，便于通过 .env 切换 Redis 地址。
celery_app = Celery(
    "sebastian",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    timezone="UTC",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    # 每个 worker 一次只预取一个任务，避免慢任务占住过多库存扫描作业。
    worker_prefetch_multiplier=1,
    beat_schedule={
        "scan-expiring-inventory-every-hour": {
            "task": "app.tasks.inventory_tasks.scan_expiring_inventory",
            "schedule": crontab(minute=0, hour="*"),
            "args": (3,),
        }
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
