"""MCP POI search tool backed by the provider layer."""

from app.providers.poi_provider import poi_provider


async def search_place(
    location: str,
    keyword: str = "",
    category: str = "",
) -> dict:
    """Search tourist attractions in a city/location."""
    return await poi_provider.search_places(city=location, keyword=keyword, category=category)
