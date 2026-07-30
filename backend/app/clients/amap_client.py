"""Amap Web Service client used by providers."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.providers.exceptions import ProviderTimeoutError, ProviderUpstreamError


class AmapClient:
    """Small typed wrapper around Amap HTTP endpoints."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.amap_api_key
        self.base_url = (base_url or settings.amap_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds or settings.provider_timeout_seconds
        self.max_retries = max_retries if max_retries is not None else settings.provider_max_retries

    async def _request_json(self, path: str, *, params: dict[str, Any]) -> dict[str, Any]:
        attempts = self.max_retries + 1
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.get(
                        f"{self.base_url}{path}",
                        params={"key": self.api_key, **params},
                    )
                    response.raise_for_status()
                    return response.json()
            except httpx.TimeoutException as exc:
                if attempt + 1 >= attempts:
                    raise ProviderTimeoutError(f"高德接口超时: {path}") from exc
            except httpx.HTTPStatusError as exc:
                if attempt + 1 >= attempts:
                    raise ProviderUpstreamError(
                        f"高德接口 HTTP {exc.response.status_code}: {path}"
                    ) from exc
            except httpx.HTTPError as exc:
                if attempt + 1 >= attempts:
                    raise ProviderUpstreamError(f"高德接口请求失败: {path}") from exc

            await asyncio.sleep(0.2 * (attempt + 1))

        raise ProviderUpstreamError(f"高德接口请求失败: {path}")

    async def get_district(self, city: str) -> dict[str, Any]:
        return await self._request_json(
            "/config/district",
            params={"keywords": city, "subdistrict": 0},
        )

    async def get_weather(self, adcode: str) -> dict[str, Any]:
        return await self._request_json(
            "/weather/weatherInfo",
            params={"city": adcode, "extensions": "all"},
        )

    async def search_poi(
        self,
        *,
        city: str,
        keyword: str = "",
        types: str = "",
        offset: int = 10,
    ) -> dict[str, Any]:
        params = {
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "offset": offset,
            "extensions": "all",
        }
        if types:
            params["types"] = types
        return await self._request_json("/place/text", params=params)

    async def geocode(self, *, address: str, city: str) -> dict[str, Any]:
        return await self._request_json(
            "/geocode/geo",
            params={"address": address, "city": city},
        )

    async def get_route(
        self,
        *,
        mode: str,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> dict[str, Any]:
        mode_to_path = {
            "driving": "/direction/driving",
            "walking": "/direction/walking",
            "riding": "/direction/bicycling",
        }
        api_path = mode_to_path.get(mode, "/direction/driving")
        return await self._request_json(
            api_path,
            params={
                "origin": f"{origin[0]},{origin[1]}",
                "destination": f"{destination[0]},{destination[1]}",
            },
        )


amap_client = AmapClient()
