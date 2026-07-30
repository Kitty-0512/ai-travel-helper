"""Verify MCP client can connect and call travel tools."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.mcp.client import mcp_client


async def main() -> int:
    await mcp_client.connect()
    if not mcp_client.connected:
        print("FAIL: MCP client not connected")
        return 1

    tools = await mcp_client.list_tools()
    print("tools:", tools)
    expected = {"search_place", "get_weather", "calculate_route"}
    if not expected.issubset(set(tools)):
        print(f"FAIL: missing tools, got {tools}")
        return 1

    weather = await mcp_client.call_tool("get_weather", {"city": "杭州", "days": 2})
    if weather.get("error"):
        print("FAIL get_weather:", weather)
        return 1
    if weather.get("source") != "amap" or weather.get("is_fallback") is not False:
        print("FAIL get_weather metadata:", weather)
        return 1
    print("ok get_weather:", weather.get("city"), len(weather.get("forecasts", [])))

    places = await mcp_client.call_tool("search_place", {"location": "杭州"})
    if places.get("error"):
        print("FAIL search_place:", places)
        return 1
    if places.get("source") != "amap" or places.get("is_fallback") is not False:
        print("FAIL search_place metadata:", places)
        return 1
    print("ok search_place: pois=", len(places.get("pois", [])))

    pois = places.get("pois", [])
    if len(pois) >= 2:
        route = await mcp_client.call_tool(
            "calculate_route",
            {"start": pois[0]["name"], "end": pois[1]["name"], "city": "杭州"},
        )
        if route.get("error"):
            print("FAIL calculate_route:", route)
            return 1
        if route.get("source") != "amap" or route.get("is_fallback") is not False:
            print("FAIL calculate_route metadata:", route)
            return 1
        print("ok calculate_route:", route.get("distance_text"), route.get("duration_text"))

    await mcp_client.disconnect()
    print("ALL MCP TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
