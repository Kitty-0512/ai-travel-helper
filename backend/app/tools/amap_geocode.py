"""高德地理编码 —— 地名 → 经纬度"""

import httpx
from app.core.config import settings


async def geocode(address: str, city: str) -> dict:
    """
    将地址/景点名转为经纬度。
    高德 API: https://restapi.amap.com/v3/geocode/geo
    """
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{settings.amap_base_url}/geocode/geo",
            params={
                "key": settings.amap_api_key,
                "address": address,
                "city": city,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") != "1" or not data.get("geocodes"):
        return {"error": f"地理编码失败: {data.get('info', '')}", "lng": 0, "lat": 0}

    geo = data["geocodes"][0]
    loc = geo.get("location", "0,0").split(",")

    return {
        "address": geo.get("formatted_address", address),
        "lng": float(loc[0]) if len(loc) == 2 else 0,
        "lat": float(loc[1]) if len(loc) == 2 else 0,
        "city": geo.get("city", city),
        "district": geo.get("district", ""),
    }
