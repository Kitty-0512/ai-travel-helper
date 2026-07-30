"""Unified route provider with fallback support."""

from __future__ import annotations

from app.clients.amap_client import AmapClient, amap_client
from app.core.config import settings
from app.providers.base import BaseProvider
from app.providers.exceptions import (
    ProviderEmptyResultError,
    ProviderUpstreamError,
    ProviderValidationError,
)
from app.providers.fallback import ProviderFallbacks, fallbacks


class RouteProvider(BaseProvider):
    def __init__(
        self,
        *,
        client: AmapClient | None = None,
        fallback_store: ProviderFallbacks | None = None,
    ) -> None:
        self.client = client or amap_client
        self.fallback_store = fallback_store or fallbacks

    async def calculate_route(
        self,
        origin: str,
        destination: str,
        city: str,
        mode: str = "driving",
    ) -> dict:
        normalized_mode = mode if mode in {"driving", "walking", "riding"} else "driving"
        cache_key = f"route:{city}:{normalized_mode}:{origin}:{destination}"
        try:
            origin_coord = await self._geocode(city=city, place=origin)
            dest_coord = await self._geocode(city=city, place=destination)

            route_data = await self.client.get_route(
                mode=normalized_mode,
                origin=origin_coord,
                destination=dest_coord,
            )
            if route_data.get("status") != "1":
                raise ProviderUpstreamError(
                    f"路径规划失败: {route_data.get('info', '未知错误')}"
                )

            paths = route_data.get("route", {}).get("paths", [])
            if not paths:
                raise ProviderEmptyResultError("未找到可行路径")

            path = paths[0]
            payload = {
                "origin": origin,
                "destination": destination,
                "mode": normalized_mode,
                "distance_meters": int(path.get("distance", 0)),
                "duration_seconds": int(path.get("duration", 0)),
                "distance_text": f"{int(path.get('distance', 0)) / 1000:.1f} km",
                "duration_text": f"{int(path.get('duration', 0)) // 60} 分钟",
            }
            self.fallback_store.remember(cache_key, payload)
            return self.success(payload)
        except Exception as exc:
            if not self.fallback_enabled:
                if isinstance(
                    exc,
                    (ProviderUpstreamError, ProviderEmptyResultError, ProviderValidationError),
                ):
                    return self.error(exc)
                return self.error(ProviderUpstreamError(str(exc)))

            fallback_payload = self.fallback_store.route_fallback(
                city,
                origin,
                destination,
                normalized_mode,
                settings.provider_cache_ttl_seconds,
            )
            return self.fallback_success(
                fallback_payload,
                message=f"实时路线不可用，已返回备用结果: {exc}",
                error_code=getattr(exc, "code", "fallback_used"),
            )

    async def _geocode(self, *, city: str, place: str) -> tuple[float, float]:
        if not place:
            raise ProviderValidationError("起点或终点不能为空")

        data = await self.client.geocode(address=place, city=city)
        if data.get("status") != "1" or not data.get("geocodes"):
            raise ProviderUpstreamError(f"无法定位地点: {place}")

        location = data["geocodes"][0].get("location", "")
        loc = location.split(",")
        if len(loc) != 2:
            raise ProviderEmptyResultError(f"坐标返回为空: {place}")

        coord = (float(loc[0]), float(loc[1]))
        self.fallback_store.remember_geocode(city, place, coord)
        return coord


route_provider = RouteProvider()
