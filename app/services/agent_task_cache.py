from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import get_settings
from app.integrations.redis_client import get_redis_client


def _task_key(task_id: str) -> str:
    return f"agent:task:{task_id}:status"


def set_agent_task_status(
    task_id: str,
    status: str,
    *,
    user_id: str | None = None,
    detail: dict | None = None,
) -> bool:
    settings = get_settings()
    payload = {
        "task_id": task_id,
        "status": status,
        "user_id": user_id,
        "detail": detail or {},
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        client = get_redis_client()
        client.set(_task_key(task_id), json.dumps(payload), ex=settings.agent_task_status_ttl_seconds)
        return True
    except Exception:
        # Cache write failures should not break the request path.
        return False


def get_agent_task_status(task_id: str) -> dict | None:
    try:
        client = get_redis_client()
        raw = client.get(_task_key(task_id))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None
