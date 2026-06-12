from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.core.config import Settings, get_settings
from app.db.session import check_database_health
from app.integrations.elasticsearch_client import check_elasticsearch_health
from app.integrations.redis_client import check_redis_health


router = APIRouter()


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "app": settings.app_name, "environment": settings.app_env}


@router.get("/health/dependencies")
def dependencies_health() -> dict[str, object]:
    postgres_status = check_database_health()
    redis_status = check_redis_health()
    es_status = check_elasticsearch_health()
    statuses = {postgres_status["status"], redis_status["status"], es_status["status"]}

    if statuses == {"ok"}:
        overall = "ok"
    elif "error" in statuses:
        overall = "degraded"
    else:
        overall = "partial"

    return {"status": overall, "postgres": postgres_status, "redis": redis_status, "elasticsearch": es_status}


@router.get("/health/readiness")
def readiness_health() -> JSONResponse:
    payload = dependencies_health()
    http_status = 200 if payload["status"] == "ok" else 503
    return JSONResponse(status_code=http_status, content=payload)
