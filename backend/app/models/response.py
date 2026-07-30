"""SSE 事件模型 & 响应类型"""

from dataclasses import dataclass, field
from typing import Any
import orjson


@dataclass
class SSEEvent:
    """
    统一的 SSE 事件。
    序列化为:
        event: {type}
        data: {json}
        id: {id}
    """
    type: str
    data: Any = None
    id: int = 0  # 自增序号

    _counter: int = field(default=0, init=False, repr=False)

    def to_sse(self) -> str:
        """转为 SSE 文本行"""
        payload = orjson.dumps(self.data, default=str).decode("utf-8") if self.data is not None else "{}"
        lines = [
            f"event: {self.type}",
            f"data: {payload}",
            f"id: {self.id}",
            "",
            "",
        ]
        return "\n".join(lines)


# ============================================================
# SSE 事件类型的 data 子结构（方便类型提示）
# ============================================================

@dataclass
class ToolCallData:
    type: str
    tool: str
    status: str
    message: str
    args: dict


@dataclass
class ToolResultData:
    tool: str
    status: str
    message: str
    duration: int
    result_preview: dict


@dataclass
class DoneData:
    request_id: str
    destination: str
    days: int
    places_count: int
    places_detail: list
    session_id: str


@dataclass
class ErrorData:
    code: str
    message: str
