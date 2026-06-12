from __future__ import annotations

from app.core.config import get_settings
from app.integrations.redis_client import get_redis_client


def _rate_limit_key(user_id: str) -> str:
    return f"agent:rate_limit:{user_id}"


def check_agent_rate_limit(user_id: str) -> bool:
    """Return True when request can continue.

    Fail-open strategy: if Redis is unavailable, do not block the request path.
    """
    settings = get_settings()
    key = _rate_limit_key(user_id)

    try:
        client = get_redis_client()
        current = int(client.incr(key))
        if current == 1:
            client.expire(key, settings.agent_rate_limit_window_seconds)
        return current <= settings.agent_rate_limit_max_requests
    except Exception:
        return True
