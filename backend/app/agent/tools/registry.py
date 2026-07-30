"""Planner task tool adapters."""

TOOL_NAME_MAP: dict[str, str] = {
    "weather": "get_weather",
    "poi_search": "search_place",
    "route": "calculate_route",
    "flight_search": "search_flights",
    "hotel_search": "search_hotels",
}


def resolve_tool_name(tool_name: str) -> str:
    """Map planner-facing tool ids to concrete tool names (MCP or local)."""
    return TOOL_NAME_MAP.get(tool_name, tool_name)
