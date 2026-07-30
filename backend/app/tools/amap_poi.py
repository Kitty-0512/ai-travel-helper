"""高德 POI 兼容层，实际实现走 Provider。"""

from app.providers.poi_provider import poi_provider


async def search_pois(
    city: str,
    keyword: str = "",
    category: str = "",
) -> dict:
    """搜索指定城市的旅游景点。"""
    return await poi_provider.search_places(city=city, keyword=keyword, category=category)
