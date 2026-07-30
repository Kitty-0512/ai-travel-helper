"""Trace HTTP API — GET /api/trace/{request_id}."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Security
from pydantic import BaseModel

from app.core.security import verify_api_key
from app.core.limiter import default_limiter
from app.core.user_id import require_user_id
from app.trace.storage import trace_storage

router = APIRouter()


class TraceStep(BaseModel):
    id: str
    request_id: str
    user_id: str | None = None
    step: int
    action: str
    tool_name: str | None = None
    input: dict[str, Any]
    output: dict[str, Any]
    duration: int
    status: str
    created_time: str | None = None


class TraceResponse(BaseModel):
    request_id: str
    available: bool
    backend: str
    steps: list[TraceStep]


@router.get("/{request_id}", response_model=TraceResponse)
async def get_trace(
    request_id: str,
    _api_key: str = Security(verify_api_key),
    _rl: None = Depends(default_limiter),
    user_id: str = Depends(require_user_id),
):
    records = await trace_storage.list_by_request_id(request_id, user_id)
    return TraceResponse(
        request_id=request_id,
        available=trace_storage.ready,
        backend=trace_storage.backend,
        steps=[
            TraceStep(
                id=str(r.id),
                request_id=r.request_id,
                user_id=r.user_id,
                step=r.step,
                action=r.action,
                tool_name=r.tool_name,
                input=r.input,
                output=r.output,
                duration=r.duration,
                status=r.status,
                created_time=r.created_time.isoformat() if r.created_time else None,
            )
            for r in records
        ],
    )
