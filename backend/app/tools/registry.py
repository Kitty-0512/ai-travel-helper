"""工具注册表 —— 本地工具 + MCP 工具 schema 合并"""

from app.tools.search_flight import search_flights
from app.tools.search_hotel import search_hotels
from app.mcp.registry import get_mcp_schemas
from app.mcp.client import mcp_client

# ── 本地函数注册表（仅 mock 机票/酒店）──
TOOL_REGISTRY: dict[str, callable] = {
    "search_flights": search_flights,
    "search_hotels": search_hotels,
}

# ── 本地 OpenAI-compatible Tool Schema ──
LOCAL_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": (
                "搜索从指定出发地到目的地的机票信息。返回航班号、航司、起降时间、价格区间。"
                "⚠️ 当前为 Mock 数据，仅供参考行程交通成本。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "from_city": {
                        "type": "string",
                        "description": "出发城市，如'上海'",
                    },
                    "to_city": {
                        "type": "string",
                        "description": "目的城市，如'北京'",
                    },
                    "date": {
                        "type": "string",
                        "description": "出发日期，格式 YYYY-MM-DD，可留空",
                    },
                },
                "required": ["from_city", "to_city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": (
                "搜索指定城市/区域的酒店信息。返回酒店名称、位置、价格区间、评分、特色。"
                "⚠️ 当前为 Mock 数据，仅供参考住宿选择。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "目标城市",
                    },
                    "area": {
                        "type": "string",
                        "description": "偏好区域，如'市中心'、'西湖附近'，可留空",
                    },
                    "budget": {
                        "type": "string",
                        "enum": ["经济", "舒适", "高档", "奢华"],
                        "description": "预算等级，可留空",
                    },
                },
                "required": ["city"],
            },
        },
    },
]


def build_tools_schema() -> list[dict]:
    """合并 MCP 旅行工具 schema + 本地 mock 工具 schema。"""
    schemas = [dict(t) for t in LOCAL_TOOL_SCHEMAS]
    if mcp_client.connected:
        schemas.extend(get_mcp_schemas())
    return schemas
