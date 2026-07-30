"""MCP weather tool backed by the provider layer."""

from app.providers.weather_provider import weather_provider


async def get_weather(city: str, days: int = 3) -> dict:
    """Query weather forecast for a city."""
    return await weather_provider.get_weather(city=city, days=days)
