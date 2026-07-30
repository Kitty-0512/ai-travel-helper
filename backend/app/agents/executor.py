"""Agent Executor —— 解析 tool_calls → MCP / local 执行 → 收集结果"""

import json
import asyncio

from app.core.config import settings
from app.mcp.dispatcher import execute_tool


def _is_retryable_error(result: dict) -> bool:
    """Only retry transient upstream failures, not validation errors."""
    if not isinstance(result, dict):
        return False
    error = str(result.get("error", "")).lower()
    if not error:
        return False
    non_retryable = ("未知工具", "参数", "validation", "invalid", "不能为空")
    if any(token in error for token in non_retryable):
        return False
    retryable = ("超时", "timeout", "不可用", "upstream", "mcp", "连接", "503", "502", "429")
    return any(token in error for token in retryable)


async def execute_tool_calls(
    tool_calls: list[dict],
) -> list[dict]:
    """
    并行执行多个工具调用，每个带超时和重试。

    返回:
        [{"tool_call_id": "xxx", "tool_name": "search_place", "result": {...}}, ...]
    """
    async def _run_one(tc: dict) -> dict:
        tc_id = tc.get("id", "")
        func = tc.get("function", {})
        name = func.get("name", "")
        try:
            args = json.loads(func.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}

        last_error = None
        source = "local"
        duration_ms = 0
        for attempt in range(settings.tool_max_retries + 1):
            result, source, duration_ms = await execute_tool(name, args)
            if not (isinstance(result, dict) and result.get("error")):
                return {
                    "tool_call_id": tc_id,
                    "tool_name": name,
                    "result": result,
                    "source": source,
                    "duration_ms": duration_ms,
                }
            last_error = result.get("error")
            if not _is_retryable_error(result) or attempt >= settings.tool_max_retries:
                break
            await asyncio.sleep(0.3 * (2**attempt))

        return {
            "tool_call_id": tc_id,
            "tool_name": name,
            "result": {"error": last_error or "未知错误"},
            "source": source,
            "duration_ms": duration_ms,
        }

    results = await asyncio.gather(*[_run_one(tc) for tc in tool_calls])
    return list(results)


def build_tool_messages(
    tool_calls: list[dict],
    tool_results: list[dict],
) -> tuple[dict, list[dict]]:
    """
    将工具调用和结果转换为可注入 messages 的格式。

    返回:
        (assistant_msg, [tool_msg, ...])
    """
    assistant_msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": tool_calls,
    }

    tool_msgs = []
    for tr in tool_results:
        tool_msgs.append({
            "role": "tool",
            "tool_call_id": tr["tool_call_id"],
            "content": json.dumps(tr["result"], ensure_ascii=False),
        })

    return assistant_msg, tool_msgs
