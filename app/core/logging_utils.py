from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


def configure_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=level, format="%(message)s")
    else:
        root_logger.setLevel(level)


def log_access_event(
    *,
    trace_id: str | None,
    user_id: str | None,
    action: str | None,
    route: str,
    method: str,
    status_code: int,
    latency_ms: int,
) -> None:
    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "message": "http_request",
        "trace_id": trace_id,
        "user_id": user_id,
        "action": action,
        "route": route,
        "method": method,
        "status_code": status_code,
        "latency_ms": latency_ms,
    }
    logging.getLogger("app.access").info(json.dumps(payload, ensure_ascii=False))