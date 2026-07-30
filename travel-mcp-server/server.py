"""Travel MCP Server — stdio transport via official MCP Python SDK."""

import sys
from pathlib import Path

# Allow importing backend/app/tools (amap implementations)
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from mcp.server.fastmcp import FastMCP

from tools.poi import search_place as _search_place
from tools.route import calculate_route as _calculate_route
from tools.weather import get_weather as _get_weather

mcp = FastMCP("travel-mcp-server")


@mcp.tool()
async def search_place(location: str, keyword: str = "", category: str = "") -> dict:
    """Search tourist attractions, parks, museums, and landmarks in a city."""
    return await _search_place(location=location, keyword=keyword, category=category)


@mcp.tool()
async def get_weather(city: str, days: int = 3) -> dict:
    """Get weather forecast for a city (up to 7 days)."""
    return await _get_weather(city=city, days=days)


@mcp.tool()
async def calculate_route(
    start: str,
    end: str,
    city: str,
    mode: str = "driving",
) -> dict:
    """Calculate driving/walking/riding distance and duration between two places."""
    return await _calculate_route(start=start, end=end, city=city, mode=mode)


if __name__ == "__main__":
    mcp.run(transport="stdio")
