from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

MCPErrorCode = Literal["RETRYABLE_ERROR", "VALIDATION_ERROR", "BUSINESS_ERROR", "FATAL_ERROR"]


class MCPToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    timeout_ms: int = 5000
    idempotency_key_required: bool = False


class MCPInvokeRequest(BaseModel):
    name: str
    input: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    trace_id: str | None = None
    user_id: str | None = Field(default=None, min_length=1, max_length=64)
    action: str = Field(default="invoke", min_length=1, max_length=64)


class MCPInvokeResponse(BaseModel):
    trace_id: str
    tool_name: str
    result: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int
    status: Literal["ok", "error"] = "ok"
    error_code: MCPErrorCode | None = None
    error_message: str | None = None
    from_cache: bool = False


class MCPToolsResponse(BaseModel):
    tools: list[MCPToolSpec] = Field(default_factory=list)


class MCPErrorResponse(BaseModel):
    code: MCPErrorCode
    message: str
    timestamp: datetime
