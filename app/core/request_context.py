from __future__ import annotations

from contextvars import ContextVar


_trace_id_ctx: ContextVar[str | None] = ContextVar("trace_id", default=None)


def set_current_trace_id(trace_id: str | None) -> None:
    _trace_id_ctx.set(trace_id)


def get_current_trace_id() -> str | None:
    return _trace_id_ctx.get()