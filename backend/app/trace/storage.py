"""PostgreSQL trace storage with in-process fallback."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import asyncpg

from app.core.config import settings
from app.trace.models import TraceRecord

logger = logging.getLogger(__name__)


def _row_to_record(row) -> TraceRecord:
    return TraceRecord(
        id=row["id"],
        request_id=row["request_id"],
        user_id=row["user_id"],
        step=row["step"],
        action=row["action"],
        tool_name=row["tool_name"],
        input=row["input"] or {},
        output=row["output"] or {},
        duration=row["duration"],
        status=row["status"],
        created_time=row["created_time"],
    )


class TraceStorage:
    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._ready = False
        self._backend = "none"  # pg | memory | none
        self._rows: list[TraceRecord] = []

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def backend(self) -> str:
        return self._backend

    async def connect(self) -> None:
        if not settings.trace_enabled:
            logger.info("[Trace] disabled by config")
            return
        try:
            self._pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=3)
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT 1")
            self._ready = True
            self._backend = "pg"
            logger.info("[Trace] PostgreSQL connected")
            return
        except Exception as e:
            logger.warning("[Trace] PostgreSQL unavailable: %s", e)
            await self._close_pool()

        if settings.trace_fallback_inprocess and not settings.is_production:
            self._ready = True
            self._backend = "memory"
            logger.warning("[Trace] using in-process fallback (non-durable)")
        else:
            self._ready = False
            self._backend = "none"

    async def _close_pool(self) -> None:
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:
                pass
            self._pool = None

    async def close(self) -> None:
        await self._close_pool()
        self._rows.clear()
        self._ready = False
        self._backend = "none"

    async def insert_trace(
        self,
        *,
        request_id: str,
        user_id: str | None,
        step: int,
        action: str,
        tool_name: str | None = None,
        input_payload: dict[str, Any] | None = None,
        output_payload: dict[str, Any] | None = None,
        duration: int = 0,
        status: str,
    ) -> TraceRecord | None:
        if not self._ready:
            return None

        input_payload = input_payload or {}
        output_payload = output_payload or {}

        if self._backend == "memory" or self._pool is None:
            return self._append_memory(
                request_id=request_id,
                user_id=user_id,
                step=step,
                action=action,
                tool_name=tool_name,
                input_payload=input_payload,
                output_payload=output_payload,
                duration=duration,
                status=status,
            )

        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO agent_trace
                        (request_id, user_id, step, action, tool_name, input, output, duration, status)
                    VALUES
                        ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9)
                    RETURNING id, request_id, user_id, step, action, tool_name,
                              input, output, duration, status, created_time
                    """,
                    request_id,
                    user_id,
                    step,
                    action,
                    tool_name,
                    json.dumps(input_payload, ensure_ascii=False, default=str),
                    json.dumps(output_payload, ensure_ascii=False, default=str),
                    duration,
                    status,
                )
            return _row_to_record(row)
        except Exception as e:
            logger.warning("[Trace] insert failed: %s", e)
            if settings.trace_fallback_inprocess:
                return self._append_memory(
                    request_id=request_id,
                    user_id=user_id,
                    step=step,
                    action=action,
                    tool_name=tool_name,
                    input_payload=input_payload,
                    output_payload=output_payload,
                    duration=duration,
                    status=status,
                )
            return None

    def _append_memory(
        self,
        *,
        request_id: str,
        user_id: str | None,
        step: int,
        action: str,
        tool_name: str | None,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
        duration: int,
        status: str,
    ) -> TraceRecord:
        record = TraceRecord(
            id=uuid4(),
            request_id=request_id,
            user_id=user_id,
            step=step,
            action=action,
            tool_name=tool_name,
            input=dict(input_payload),
            output=dict(output_payload),
            duration=duration,
            status=status,
            created_time=datetime.now(timezone.utc),
        )
        self._rows.append(record)
        return record

    async def list_by_request_id(self, request_id: str, user_id: str | None) -> list[TraceRecord]:
        if not self._ready:
            return []
        if self._backend == "memory" or self._pool is None:
            rows = [r for r in self._rows if r.request_id == request_id and r.user_id == user_id]
            return sorted(rows, key=lambda r: r.step)

        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, request_id, user_id, step, action, tool_name, input, output,
                           duration, status, created_time
                    FROM agent_trace
                    WHERE request_id = $1 AND ($2::varchar IS NULL OR user_id = $2)
                    ORDER BY step ASC, created_time ASC
                    """,
                    request_id,
                    user_id,
                )
            return [_row_to_record(r) for r in rows]
        except Exception as e:
            logger.warning("[Trace] query failed: %s", e)
            if settings.trace_fallback_inprocess:
                rows = [r for r in self._rows if r.request_id == request_id and r.user_id == user_id]
                return sorted(rows, key=lambda r: r.step)
            return []


trace_storage = TraceStorage()
