"""Unified POI provider with fallback support."""

from __future__ import annotations

from app.clients.amap_client import AmapClient, amap_client
from app.core.config import settings
from app.providers.base import BaseProvider
from app.providers.exceptions import ProviderEmptyResultError, ProviderUpstreamError
from app.providers.fallback import ProviderFallbacks, fallbacks

CATEGORY_MAP = {
    "景点": "风景名胜",
    "公园": "公园广场",
    "博物馆": "博物馆",
    "购物": "购物中心",
    "美食": "餐饮",
    "古迹": "风景名胜|国家级景点",
    "自然": "风景名胜|公园广场",
}


class PoiProvider(BaseProvider):
    def __init__(
        self,
        *,
        client: AmapClient | None = None,
        fallback_store: ProviderFallbacks | None = None,
    ) -> None:
        self.client = client or amap_client
        self.fallback_store = fallback_store or fallbacks

    async def search_places(self, city: str, keyword: str = "", category: str = "") -> dict:
        if not keyword and not category:
            keyword = "热门景点"

        cache_key = f"poi:{city}:{keyword}:{category}"
        try:
            payload = await self._query(city=city, keyword=keyword, category=category)
            self.fallback_store.remember(cache_key, payload)
            for poi in payload.get("pois", []):
                if poi.get("lng") and poi.get("lat") and poi.get("name"):
                    self.fallback_store.remember_geocode(
                        city,
                        poi["name"],
                        (float(poi["lng"]), float(poi["lat"])),
                    )
            return self.success(payload)
        except ProviderEmptyResultError:
            # Retry once with weaker filters before falling back.
            if category and keyword:
                retry_keyword = keyword
                retry_category = ""
            elif category:
                retry_keyword = keyword or "热门景点"
                retry_category = ""
            else:
                retry_keyword = ""
                retry_category = ""

            try:
                payload = await self._query(
                    city=city,
                    keyword=retry_keyword,
                    category=retry_category,
                )
                self.fallback_store.remember(cache_key, payload)
                return self.success(payload)
            except Exception as exc:
                return self._fallback(city, keyword, category, exc)
        except Exception as exc:
            return self._fallback(city, keyword, category, exc)

    async def _query(self, *, city: str, keyword: str, category: str) -> dict:
        data = await self.client.search_poi(
            city=city,
            keyword=keyword or "",
            types=CATEGORY_MAP.get(category, ""),
            offset=10,
        )
        if data.get("status") != "1":
            raise ProviderUpstreamError(f"POI 搜索失败: {data.get('info', '未知错误')}")

        pois = []
        for p in data.get("pois", []):
            loc = p.get("location", "0,0").split(",")
            pois.append(
                {
                    "name": p.get("name", ""),
                    "address": p.get("address", ""),
                    "lng": float(loc[0]) if len(loc) == 2 else 0,
                    "lat": float(loc[1]) if len(loc) == 2 else 0,
                    "category": p.get("type", ""),
                    "rating": p.get("biz_ext", {}).get("rating", ""),
                }
            )

        if not pois:
            raise ProviderEmptyResultError(f"POI 搜索为空: {city}")

        return {"pois": pois, "total": int(data.get("count", 0)), "city": city}

    def _fallback(self, city: str, keyword: str, category: str, exc: Exception) -> dict:
        if not self.fallback_enabled:
            if isinstance(exc, (ProviderUpstreamError, ProviderEmptyResultError)):
                return self.error(exc)
            return self.error(ProviderUpstreamError(str(exc)))

        fallback_payload = self.fallback_store.poi_fallback(
            city,
            keyword,
            category,
            settings.provider_cache_ttl_seconds,
        )
        return self.fallback_success(
            fallback_payload,
            message=f"POI 实时数据暂不可用，已返回备用结果: {exc}",
            error_code=getattr(exc, "code", "fallback_used"),
        )


poi_provider = PoiProvider()
