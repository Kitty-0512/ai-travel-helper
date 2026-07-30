"""High-level trace manager API."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.trace.context import (
    bind_trace_context,
    clear_trace_context,
    get_request_id,
    get_user_id,
    has_trace_context,
    next_step,
)
from app.trace.storage import trace_storage


class TraceManager:
    @property
    def available(self) -> bool:
        return trace_storage.ready

    async def startup(self) -> None:
        await trace_storage.connect()

    async def shutdown(self) -> None:
        await trace_storage.close()

    async def start_trace(
        self,
        *,
        request_id: str,
        user_id: str | None,
        action: str = "request_start",
        input_payload: dict[str, Any] | None = None,
        status: str = "running",
    ) -> None:
        if not settings.trace_enabled:
            return
        bind_trace_context(request_id, user_id)
        await trace_storage.insert_trace(
            request_id=request_id,
            user_id=user_id,
            step=next_step(),
            action=action,
            input_payload=input_payload,
            output_payload={},
            duration=0,
            status=status,
        )

    async def record_step(
        self,
        *,
        action: str,
        tool_name: str | None = None,
        input_payload: dict[str, Any] | None = None,
        output_payload: dict[str, Any] | None = None,
        duration: int = 0,
        status: str = "success",
    ) -> None:
        if not settings.trace_enabled or not has_trace_context():
            return
        request_id = get_request_id()
        if not request_id:
            return
        await trace_storage.insert_trace(
            request_id=request_id,
            user_id=get_user_id(),
            step=next_step(),
            action=action,
            tool_name=tool_name,
            input_payload=input_payload,
            output_payload=output_payload,
            duration=duration,
            status=status,
        )

    async def finish_trace(
        self,
        *,
        status: str,
        output_payload: dict[str, Any] | None = None,
        action: str = "request_finish",
    ) -> None:
        if not settings.trace_enabled or not has_trace_context():
            clear_trace_context()
            return
        try:
            await self.record_step(
                action=action,
                output_payload=output_payload,
                status=status,
            )
        finally:
            clear_trace_context()


trace_manager = TraceManager()
