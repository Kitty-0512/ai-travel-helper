"""高德天气兼容层，实际实现走 Provider。"""

from app.providers.weather_provider import weather_provider


async def get_weather(city: str, days: int = 3) -> dict:
    """查询指定城市天气。"""
    return await weather_provider.get_weather(city=city, days=days)
