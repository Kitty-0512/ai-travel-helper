"""Fallback helpers and lightweight in-process cache."""

from __future__ import annotations

import math
import time
from typing import Any


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lon1, lat1 = map(math.radians, a)
    lon2, lat2 = map(math.radians, b)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    hav = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(hav))


class ProviderFallbacks:
    """Process-local cache and seed data for degraded mode."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._geocode_cache: dict[str, tuple[float, float]] = {}

    def remember(self, key: str, data: dict[str, Any]) -> None:
        self._cache[key] = (time.time(), dict(data))

    def recall(self, key: str, ttl_seconds: int) -> dict[str, Any] | None:
        item = self._cache.get(key)
        if not item:
            return None
        ts, data = item
        if time.time() - ts > ttl_seconds:
            self._cache.pop(key, None)
            return None
        return dict(data)

    def remember_geocode(self, city: str, place: str, coord: tuple[float, float]) -> None:
        self._geocode_cache[f"{city}:{place}"] = coord

    def recall_geocode(self, city: str, place: str) -> tuple[float, float] | None:
        return self._geocode_cache.get(f"{city}:{place}")

    def weather_fallback(self, city: str, days: int, ttl_seconds: int) -> dict[str, Any]:
        cache_key = f"weather:{city}:{days}"
        cached = self.recall(cache_key, ttl_seconds)
        if cached:
            return cached

        city_templates = {
            "杭州": ("多云", "阵雨"),
            "上海": ("多云", "晴"),
            "北京": ("晴", "多云"),
        }
        day_weather, night_weather = city_templates.get(city, ("天气暂不可用", "天气暂不可用"))
        forecasts = []
        for offset in range(max(days, 1)):
            forecasts.append(
                {
                    "date": f"fallback-day-{offset + 1}",
                    "week": "",
                    "day_weather": day_weather,
                    "night_weather": night_weather,
                    "day_temp": "",
                    "night_temp": "",
                    "wind": "",
                    "humidity": "",
                }
            )
        return {
            "city": city,
            "forecasts": forecasts,
            "report_time": "",
        }

    def poi_fallback(self, city: str, keyword: str, category: str, ttl_seconds: int) -> dict[str, Any]:
        cache_key = f"poi:{city}:{keyword}:{category}"
        cached = self.recall(cache_key, ttl_seconds)
        if cached:
            return cached

        seeds: dict[str, list[dict[str, Any]]] = {
            "杭州": [
                {"name": "西湖", "address": "杭州市西湖风景名胜区", "lng": 120.1551, "lat": 30.2741, "category": "风景名胜", "rating": "4.9"},
                {"name": "灵隐寺", "address": "杭州市西湖区灵隐路法云弄1号", "lng": 120.1014, "lat": 30.2408, "category": "古迹", "rating": "4.8"},
                {"name": "西溪国家湿地公园", "address": "杭州市西湖区天目山路518号", "lng": 120.0612, "lat": 30.2551, "category": "自然", "rating": "4.8"},
            ],
            "上海": [
                {"name": "外滩", "address": "上海市黄浦区中山东一路", "lng": 121.4903, "lat": 31.2417, "category": "景点", "rating": "4.8"},
                {"name": "豫园", "address": "上海市黄浦区福佑路168号", "lng": 121.4925, "lat": 31.2272, "category": "古迹", "rating": "4.7"},
                {"name": "上海博物馆", "address": "上海市黄浦区人民大道201号", "lng": 121.4752, "lat": 31.2304, "category": "博物馆", "rating": "4.8"},
            ],
            "北京": [
                {"name": "故宫博物院", "address": "北京市东城区景山前街4号", "lng": 116.3970, "lat": 39.9187, "category": "古迹", "rating": "4.9"},
                {"name": "天坛公园", "address": "北京市东城区天坛东路甲1号", "lng": 116.4173, "lat": 39.8822, "category": "公园", "rating": "4.8"},
                {"name": "颐和园", "address": "北京市海淀区新建宫门路19号", "lng": 116.2730, "lat": 39.9996, "category": "景点", "rating": "4.8"},
            ],
        }
        pois = seeds.get(city, [])
        return {"pois": pois, "total": len(pois), "city": city}

    def route_fallback(
        self,
        city: str,
        origin: str,
        destination: str,
        mode: str,
        ttl_seconds: int,
    ) -> dict[str, Any]:
        cache_key = f"route:{city}:{mode}:{origin}:{destination}"
        cached = self.recall(cache_key, ttl_seconds)
        if cached:
            return cached

        start = self.recall_geocode(city, origin)
        end = self.recall_geocode(city, destination)
        if start and end:
            distance_km = _haversine_km(start, end)
            speed_kmh = {"walking": 5, "riding": 15, "driving": 30}.get(mode, 30)
            duration_minutes = max(int(distance_km / max(speed_kmh, 1) * 60), 1)
            return {
                "origin": origin,
                "destination": destination,
                "mode": mode,
                "distance_meters": int(distance_km * 1000),
                "duration_seconds": duration_minutes * 60,
                "distance_text": f"{distance_km:.1f} km",
                "duration_text": f"{duration_minutes} 分钟（估算）",
            }

        return {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "distance_meters": 0,
            "duration_seconds": 0,
            "distance_text": "未知",
            "duration_text": "未知",
        }


fallbacks = ProviderFallbacks()
