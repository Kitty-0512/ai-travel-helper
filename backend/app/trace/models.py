"""Trace persistence models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(slots=True)
class TraceRecord:
    id: UUID
    request_id: str
    user_id: str | None
    step: int
    action: str
    tool_name: str | None
    input: dict[str, Any]
    output: dict[str, Any]
    duration: int
    status: str
    created_time: datetime | None
