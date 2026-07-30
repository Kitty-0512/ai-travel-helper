"""Request-local trace context powered by contextvars."""

from __future__ import annotations

from contextvars import ContextVar

_request_id_var: ContextVar[str | None] = ContextVar("trace_request_id", default=None)
_user_id_var: ContextVar[str | None] = ContextVar("trace_user_id", default=None)
_step_var: ContextVar[int] = ContextVar("trace_step", default=1)


def bind_trace_context(request_id: str, user_id: str | None) -> None:
    _request_id_var.set(request_id)
    _user_id_var.set(user_id)
    _step_var.set(1)


def clear_trace_context() -> None:
    _request_id_var.set(None)
    _user_id_var.set(None)
    _step_var.set(1)


def get_request_id() -> str | None:
    return _request_id_var.get()


def get_user_id() -> str | None:
    return _user_id_var.get()


def has_trace_context() -> bool:
    return get_request_id() is not None


def next_step() -> int:
    current = _step_var.get()
    _step_var.set(current + 1)
    return current
