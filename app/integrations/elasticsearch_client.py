from __future__ import annotations

from functools import lru_cache

from elasticsearch import Elasticsearch

from app.core.config import get_settings


@lru_cache(maxsize=1)
def get_elasticsearch_client() -> Elasticsearch:
    settings = get_settings()
    return Elasticsearch(hosts=[settings.elasticsearch_url], request_timeout=3)


def check_elasticsearch_health() -> dict[str, str]:
    try:
        client = get_elasticsearch_client()
        ok = bool(client.ping())
        return {"status": "ok" if ok else "degraded", "detail": "ping ok" if ok else "ping false"}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
