from __future__ import annotations

from functools import lru_cache

import redis

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def check_redis_health() -> dict[str, str]:
    try:
        client = get_redis_client()
        pong = client.ping()
        return {"status": "ok" if pong else "degraded", "detail": "pong" if pong else "no pong"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
