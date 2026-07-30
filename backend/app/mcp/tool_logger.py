"""Structured logging for local and MCP tool invocations."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings

logger = logging.getLogger("tool_calls")


def _truncate(value: Any, max_len: int = 2000) -> Any:
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "...(truncated)"
    if isinstance(value, dict):
        return {k: _truncate(v, max_len) for k, v in list(value.items())[:20]}
    if isinstance(value, list) and len(value) > 10:
        return value[:10] + ["...(truncated)"]
    return value


def log_tool_call(
    tool_name: str,
    input_args: dict[str, Any],
    output: Any,
    duration_ms: float,
    source: str,
) -> None:
    """Record tool_name, input, output, duration to stdout and optional JSONL file."""
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "tool_name": tool_name,
        "input": _truncate(input_args),
        "output": _truncate(output),
        "duration_ms": round(duration_ms, 2),
    }
    logger.info(
        "[ToolCall] %s %s %.0fms",
        source,
        tool_name,
        duration_ms,
    )
    path = (settings.mcp_tool_log_path or "").strip()
    if not path:
        return
    try:
        log_file = Path(path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception as e:
        logger.warning("[ToolCall] failed to write log file: %s", e)


class ToolCallTimer:
    """Context manager for timing tool calls."""

    def __init__(self) -> None:
        self._start = 0.0

    def __enter__(self) -> "ToolCallTimer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:
        pass

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000
