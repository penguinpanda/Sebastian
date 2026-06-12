from __future__ import annotations

import json
from datetime import datetime, timezone

from app.integrations.redis_client import get_redis_client

QUEUE_KEY = "agent:task_queue"


def enqueue_agent_task(task_id: str, user_id: str | None, message: str, trace_id: str | None = None) -> bool:
    payload = {
        "task_id": task_id,
        "user_id": user_id,
        "message": message,
        "trace_id": trace_id,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        client = get_redis_client()
        client.rpush(QUEUE_KEY, json.dumps(payload))
        return True
    except Exception:
        return False


def dequeue_agent_task() -> dict | None:
    try:
        client = get_redis_client()
        raw = client.lpop(QUEUE_KEY)
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def get_agent_queue_size() -> int:
    try:
        client = get_redis_client()
        return int(client.llen(QUEUE_KEY))
    except Exception:
        return 0
