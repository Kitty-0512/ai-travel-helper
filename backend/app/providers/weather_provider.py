"""Unified weather provider with fallback support."""

from __future__ import annotations

from app.clients.amap_client import AmapClient, amap_client
from app.core.config import settings
from app.providers.base import BaseProvider
from app.providers.exceptions import ProviderEmptyResultError, ProviderUpstreamError
from app.providers.fallback import ProviderFallbacks, fallbacks


class WeatherProvider(BaseProvider):
    def __init__(
        self,
        *,
        client: AmapClient | None = None,
        fallback_store: ProviderFallbacks | None = None,
    ) -> None:
        self.client = client or amap_client
        self.fallback_store = fallback_store or fallbacks

    async def get_weather(self, city: str, days: int = 3) -> dict:
        cache_key = f"weather:{city}:{days}"
        try:
            geo_data = await self.client.get_district(city)
            if geo_data.get("status") != "1" or not geo_data.get("districts"):
                raise ProviderUpstreamError(f"未找到城市: {city}")

            adcode = geo_data["districts"][0]["adcode"]
            weather_data = await self.client.get_weather(adcode)
            if weather_data.get("status") != "1":
                raise ProviderUpstreamError(
                    f"天气查询失败: {weather_data.get('info', '未知错误')}"
                )

            forecasts = weather_data.get("forecasts", [])
            if not forecasts:
                raise ProviderEmptyResultError(f"天气返回为空: {city}")

            cast = forecasts[0].get("casts", [])
            if not cast:
                raise ProviderEmptyResultError(f"天气预报返回为空: {city}")

            payload = {
                "city": city,
                "forecasts": [
                    {
                        "date": c.get("date", ""),
                        "week": c.get("week", ""),
                        "day_weather": c.get("dayweather", ""),
                        "night_weather": c.get("nightweather", ""),
                        "day_temp": c.get("daytemp", ""),
                        "night_temp": c.get("nighttemp", ""),
                        "wind": c.get("daywind", ""),
                        "humidity": c.get("humidity", ""),
                    }
                    for c in cast[:days]
                ],
                "report_time": weather_data.get("reporttime", ""),
            }
            self.fallback_store.remember(cache_key, payload)
            return self.success(payload)
        except Exception as exc:
            if not self.fallback_enabled:
                if isinstance(exc, (ProviderUpstreamError, ProviderEmptyResultError)):
                    return self.error(exc)
                return self.error(ProviderUpstreamError(str(exc)))

            fallback_payload = self.fallback_store.weather_fallback(
                city,
                days,
                settings.provider_cache_ttl_seconds,
            )
            return self.fallback_success(
                fallback_payload,
                message=f"天气实时数据暂不可用，已返回备用结果: {exc}",
                error_code=getattr(exc, "code", "fallback_used"),
            )


weather_provider = WeatherProvider()
