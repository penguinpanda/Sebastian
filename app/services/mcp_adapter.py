from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from app.core.config import get_settings
from app.schemas.mcp import MCPErrorCode, MCPInvokeRequest, MCPInvokeResponse, MCPToolSpec
from app.services.mcp_idempotency_cache import get_cached_response, set_cached_response


class MCPInvocationError(Exception):
    """MCP 工具调用错误，携带可映射到 HTTP 响应的业务错误码。"""

    def __init__(self, code: MCPErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MCPToolAdapter:
    """把内部服务函数包装成统一的 MCP list/invoke 协议。"""

    def __init__(self, tool_specs: list[MCPToolSpec], handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]) -> None:
        self._tool_specs = {spec.name: spec for spec in tool_specs}
        self._handlers = handlers
        self._settings = get_settings()

    def list_tools(self) -> list[MCPToolSpec]:
        return list(self._tool_specs.values())

    def invoke(self, request: MCPInvokeRequest) -> MCPInvokeResponse:
        """执行一次 MCP 工具调用，包含鉴权、幂等缓存、审计和错误分类。"""
        self._authorize(request)

        spec = self._tool_specs.get(request.name)
        if spec is None:
            raise MCPInvocationError("VALIDATION_ERROR", f"Unknown tool: {request.name}")

        if spec.idempotency_key_required and not request.idempotency_key:
            raise MCPInvocationError("VALIDATION_ERROR", "idempotency_key is required for this tool")

        if request.idempotency_key:
            # 相同幂等键命中缓存时直接返回历史结果，避免重复执行有副作用的工具。
            cached = get_cached_response(request.idempotency_key)
            if cached:
                cached_result = dict(cached.get("result") or {})
                cached_result.setdefault("_audit", self._build_audit_payload(request, str(cached.get("trace_id") or request.trace_id or str(uuid4()))))
                return MCPInvokeResponse(
                    trace_id=str(cached.get("trace_id") or request.trace_id or str(uuid4())),
                    tool_name=request.name,
                    result=cached_result,
                    latency_ms=int(cached.get("latency_ms") or 0),
                    status="ok",
                    from_cache=True,
                )

        handler = self._handlers.get(request.name)
        if handler is None:
            raise MCPInvocationError("FATAL_ERROR", f"No handler registered for tool: {request.name}")

        t0 = perf_counter()
        trace_id = request.trace_id or str(uuid4())
        try:
            result = handler(request.input)
        except TimeoutError as exc:
            # 按错误类型归类，调用方可以决定是否重试或展示业务错误。
            raise MCPInvocationError("RETRYABLE_ERROR", str(exc)) from exc
        except ValueError as exc:
            raise MCPInvocationError("VALIDATION_ERROR", str(exc)) from exc
        except RuntimeError as exc:
            raise MCPInvocationError("BUSINESS_ERROR", str(exc)) from exc
        except Exception as exc:
            raise MCPInvocationError("FATAL_ERROR", str(exc)) from exc

        latency_ms = int((perf_counter() - t0) * 1000)
        result_with_audit = dict(result)
        result_with_audit["_audit"] = self._build_audit_payload(request, trace_id)
        response = MCPInvokeResponse(
            trace_id=trace_id,
            tool_name=request.name,
            result=result_with_audit,
            latency_ms=latency_ms,
            status="ok",
            from_cache=False,
        )

        if request.idempotency_key:
            set_cached_response(
                request.idempotency_key,
                {
                    "trace_id": trace_id,
                    "tool_name": request.name,
                    "result": result_with_audit,
                    "latency_ms": latency_ms,
                    "cached_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        return response

    def _authorize(self, request: MCPInvokeRequest) -> None:
        """按配置决定是否启用轻量 MCP 鉴权和 action 白名单。"""
        if not self._settings.mcp_auth_enabled:
            return

        if not request.user_id:
            raise MCPInvocationError("VALIDATION_ERROR", "user_id is required when MCP auth is enabled")

        allowed_actions = {item.strip() for item in self._settings.mcp_allowed_actions.split(",") if item.strip()}
        if allowed_actions and request.action not in allowed_actions:
            raise MCPInvocationError("BUSINESS_ERROR", f"action not allowed: {request.action}")

    @staticmethod
    def _build_audit_payload(request: MCPInvokeRequest, trace_id: str) -> dict[str, Any]:
        """写入工具结果中的审计字段，便于跨系统追踪一次调用。"""
        return {
            "trace_id": trace_id,
            "user_id": request.user_id,
            "action": request.action,
            "tool_name": request.name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
