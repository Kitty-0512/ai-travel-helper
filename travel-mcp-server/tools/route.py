"""MCP route tool backed by the provider layer."""

from app.providers.route_provider import route_provider


async def calculate_route(
    start: str,
    end: str,
    city: str,
    mode: str = "driving",
) -> dict:
    """Calculate distance and duration between two places."""
    return await route_provider.calculate_route(
        origin=start,
        destination=end,
        city=city,
        mode=mode,
    )
