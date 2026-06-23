from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.requests import Request

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import LLMUnavailableError, ValidationError
from app.core.logging_utils import configure_logging, log_access_event
from app.core.request_context import set_current_trace_id


settings = get_settings()
configure_logging(settings.log_level)
# 将逗号分隔的 CORS 配置统一转成列表，避免环境变量里多余空格影响匹配。
allowed_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """为每个请求补齐 trace_id，并在响应和结构化日志里保持同一个追踪标识。"""
    started_at = datetime.now(timezone.utc)
    incoming_trace_id = request.headers.get("x-trace-id")
    trace_id = incoming_trace_id or str(uuid4())
    request.state.trace_id = trace_id
    set_current_trace_id(trace_id)

    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        # 异常路径也要记录访问日志，方便排查 500 错误发生在哪个路由和 trace。
        latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        route = getattr(getattr(request, "scope", {}).get("route", None), "path", request.url.path)
        log_access_event(
            trace_id=trace_id,
            user_id=getattr(request.state, "user_id", None),
            action=getattr(request.state, "action", request.method.lower()),
            route=route,
            method=request.method,
            status_code=500,
            latency_ms=latency_ms,
        )
        raise

    response.headers["x-trace-id"] = trace_id

    latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
    route = getattr(getattr(request, "scope", {}).get("route", None), "path", request.url.path)
    log_access_event(
        trace_id=trace_id,
        user_id=getattr(request.state, "user_id", None),
        action=getattr(request.state, "action", request.method.lower()),
        route=route,
        method=request.method,
        status_code=status_code,
        latency_ms=latency_ms,
    )
    return response


@app.exception_handler(LLMUnavailableError)
async def llm_unavailable_handler(request: Request, exc: LLMUnavailableError) -> JSONResponse:
    """全局异常处理器：LLM 不可用时统一返回 503 + 结构化错误。"""
    return JSONResponse(
        status_code=503,
        content={"success": False, "error": str(exc)},
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """全局异常处理器：业务校验失败统一返回 400 + 结构化错误。"""
    return JSONResponse(
        status_code=400,
        content={"success": False, "error": str(exc)},
    )


app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "environment": settings.app_env}
