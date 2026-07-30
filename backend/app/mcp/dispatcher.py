"""Route tool calls to MCP server or local registry."""

import asyncio
import inspect
from typing import Any

from app.core.config import settings
from app.mcp.client import mcp_client
from app.mcp.registry import is_mcp_tool
from app.mcp.tool_logger import ToolCallTimer, log_tool_call
from app.trace import trace_manager
from app.tools.registry import TOOL_REGISTRY


def normalize_mcp_args(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Map legacy planner arg names to MCP tool parameters."""
    normalized = dict(args)
    if tool_name == "search_place":
        if "location" not in normalized and "city" in normalized:
            normalized["location"] = normalized.pop("city")
    elif tool_name == "calculate_route":
        if "start" not in normalized and "origin" in normalized:
            normalized["start"] = normalized.pop("origin")
        if "end" not in normalized and "destination" in normalized:
            normalized["end"] = normalized.pop("destination")
    return normalized


async def execute_local_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        return {"error": f"未知工具: {name}"}
    try:
        result = await asyncio.wait_for(
            fn(**args),
            timeout=settings.tool_timeout,
        )
        return result if isinstance(result, dict) else {"value": result}
    except asyncio.TimeoutError:
        return {"error": f"工具 {name} 超时（{settings.tool_timeout}s）"}
    except TypeError:
        # Filter kwargs to match function signature
        sig = inspect.signature(fn)
        filtered = {k: v for k, v in args.items() if k in sig.parameters}
        try:
            result = await asyncio.wait_for(fn(**filtered), timeout=settings.tool_timeout)
            return result if isinstance(result, dict) else {"value": result}
        except Exception as e:
            return {"error": f"工具 {name} 错误: {str(e)}"}
    except Exception as e:
        return {"error": f"工具 {name} 错误: {str(e)}"}


async def execute_tool(name: str, args: dict[str, Any]) -> tuple[dict[str, Any], str, int]:
    """
    Execute a tool via MCP or local registry.

    Returns (result_dict, source, duration_ms).
    """
    timer = ToolCallTimer()
    await trace_manager.record_step(
        action="tool_call",
        tool_name=name,
        input_payload=args,
        status="running",
    )
    with timer:
        if is_mcp_tool(name) and mcp_client.connected:
            mcp_args = normalize_mcp_args(name, args)
            result = await mcp_client.call_tool(name, mcp_args)
            source = "mcp"
        elif name in TOOL_REGISTRY:
            result = await execute_local_tool(name, args)
            source = "local"
        elif is_mcp_tool(name):
            result = {"error": f"MCP 工具 {name} 不可用（MCP Server 未连接）"}
            source = "mcp"
        else:
            result = {"error": f"未知工具: {name}"}
            source = "local"

    duration_ms = round(timer.elapsed_ms)
    log_tool_call(name, args, result, timer.elapsed_ms, source)
    await trace_manager.record_step(
        action="tool_result",
        tool_name=name,
        input_payload=args,
        output_payload={"source": source, **(result if isinstance(result, dict) else {"value": result})},
        duration=duration_ms,
        status="error" if isinstance(result, dict) and result.get("error") else "success",
    )
    return result, source, duration_ms
