"""Fast verification for provider success and fallback flows."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.providers.exceptions import ProviderTimeoutError
from app.providers.fallback import ProviderFallbacks
from app.providers.poi_provider import PoiProvider
from app.providers.route_provider import RouteProvider
from app.providers.weather_provider import WeatherProvider


class SuccessClient:
    async def get_district(self, city: str) -> dict:
        return {"status": "1", "districts": [{"adcode": "330100"}]}

    async def get_weather(self, adcode: str) -> dict:
        return {
            "status": "1",
            "forecasts": [
                {
                    "casts": [
                        {"date": "2026-07-28", "dayweather": "晴", "nightweather": "多云"},
                        {"date": "2026-07-29", "dayweather": "小雨", "nightweather": "多云"},
                    ]
                }
            ],
            "reporttime": "2026-07-28 12:00:00",
        }

    async def search_poi(self, *, city: str, keyword: str = "", types: str = "", offset: int = 10) -> dict:
        return {
            "status": "1",
            "count": "1",
            "pois": [
                {
                    "name": "西湖",
                    "address": "杭州市西湖风景名胜区",
                    "location": "120.1551,30.2741",
                    "type": "风景名胜",
                    "biz_ext": {"rating": "4.9"},
                }
            ],
        }

    async def geocode(self, *, address: str, city: str) -> dict:
        mapping = {
            "西湖": "120.1551,30.2741",
            "灵隐寺": "120.1014,30.2408",
        }
        return {"status": "1", "geocodes": [{"location": mapping.get(address, "120.1551,30.2741")}]}

    async def get_route(
        self,
        *,
        mode: str,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> dict:
        return {"status": "1", "route": {"paths": [{"distance": "8300", "duration": "1500"}]}}


class FailureClient(SuccessClient):
    async def get_weather(self, adcode: str) -> dict:
        raise ProviderTimeoutError("weather timeout")

    async def search_poi(self, *, city: str, keyword: str = "", types: str = "", offset: int = 10) -> dict:
        return {"status": "1", "count": "0", "pois": []}

    async def geocode(self, *, address: str, city: str) -> dict:
        return {"status": "0", "geocodes": []}


async def main() -> int:
    success_store = ProviderFallbacks()
    weather = WeatherProvider(client=SuccessClient(), fallback_store=success_store)
    poi = PoiProvider(client=SuccessClient(), fallback_store=success_store)
    route = RouteProvider(client=SuccessClient(), fallback_store=success_store)

    weather_ok = await weather.get_weather("杭州", 2)
    assert weather_ok["source"] == "amap" and not weather_ok["is_fallback"]
    print("ok: weather provider success")

    poi_ok = await poi.search_places("杭州", category="景点")
    assert poi_ok["source"] == "amap" and poi_ok["pois"]
    print("ok: poi provider success")

    route_ok = await route.calculate_route("西湖", "灵隐寺", "杭州", "riding")
    assert route_ok["source"] == "amap" and route_ok["mode"] == "riding"
    print("ok: route provider success")

    degraded_store = ProviderFallbacks()
    degraded_store.remember_geocode("杭州", "西湖", (120.1551, 30.2741))
    degraded_store.remember_geocode("杭州", "灵隐寺", (120.1014, 30.2408))

    weather_fb = WeatherProvider(client=FailureClient(), fallback_store=degraded_store)
    poi_fb = PoiProvider(client=FailureClient(), fallback_store=degraded_store)
    route_fb = RouteProvider(client=FailureClient(), fallback_store=degraded_store)

    weather_fallback = await weather_fb.get_weather("杭州", 2)
    assert weather_fallback["is_fallback"] and weather_fallback["source"] == "fallback"
    print("ok: weather fallback")

    poi_fallback = await poi_fb.search_places("杭州", category="古迹")
    assert poi_fallback["is_fallback"] and poi_fallback["pois"]
    print("ok: poi fallback")

    route_fallback = await route_fb.calculate_route("西湖", "灵隐寺", "杭州", "walking")
    assert route_fallback["is_fallback"] and route_fallback["distance_text"]
    print("ok: route fallback")

    print("ALL PROVIDER TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
