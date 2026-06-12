from __future__ import annotations

import json
from typing import Any

from app.core.config import get_settings
from app.integrations.redis_client import get_redis_client


def _cache_key(idempotency_key: str) -> str:
    return f"mcp:idempotency:{idempotency_key}"


def get_cached_response(idempotency_key: str) -> dict[str, Any] | None:
    try:
        client = get_redis_client()
        raw = client.get(_cache_key(idempotency_key))
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)
    except Exception:
        return None


def set_cached_response(idempotency_key: str, payload: dict[str, Any]) -> bool:
    settings = get_settings()
    try:
        client = get_redis_client()
        client.set(
            _cache_key(idempotency_key),
            json.dumps(payload, ensure_ascii=False),
            ex=settings.mcp_idempotency_ttl_seconds,
        )
        return True
    except Exception:
        return False
