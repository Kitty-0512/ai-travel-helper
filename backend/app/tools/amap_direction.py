"""高德路径规划兼容层，实际实现走 Provider。"""

from app.providers.route_provider import route_provider


async def plan_route(
    origin: str,
    destination: str,
    city: str,
    mode: str = "driving",
) -> dict:
    """计算两点间距离和预估时间。"""
    return await route_provider.calculate_route(
        origin=origin,
        destination=destination,
        city=city,
        mode=mode,
    )
