from __future__ import annotations

import pytest

from app.providers.exceptions import ProviderTimeoutError
from app.providers.fallback import ProviderFallbacks
from app.providers.poi_provider import PoiProvider
from app.providers.weather_provider import WeatherProvider


class FailingClient:
    async def get_district(self, city: str) -> dict:
        return {"status": "1", "districts": [{"adcode": "330100"}]}

    async def get_weather(self, adcode: str) -> dict:
        raise ProviderTimeoutError("timeout")

    async def search_poi(self, *, city: str, keyword: str = "", types: str = "", offset: int = 10) -> dict:
        return {"status": "1", "count": "0", "pois": []}


@pytest.mark.asyncio
async def test_weather_provider_uses_fallback_on_timeout():
    provider = WeatherProvider(client=FailingClient(), fallback_store=ProviderFallbacks())
    result = await provider.get_weather("杭州", 2)
    assert result["is_fallback"] is True
    assert result["source"] == "fallback"
    assert len(result["forecasts"]) == 2


@pytest.mark.asyncio
async def test_poi_provider_returns_seed_data_on_empty_response():
    provider = PoiProvider(client=FailingClient(), fallback_store=ProviderFallbacks())
    result = await provider.search_places("杭州", category="古迹")
    assert result["is_fallback"] is True
    assert result["source"] == "fallback"
    assert len(result["pois"]) >= 1
