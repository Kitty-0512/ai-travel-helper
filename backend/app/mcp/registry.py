"""MCP tool schemas exposed to the LLM."""

MCP_TOOL_NAMES = frozenset({"search_place", "get_weather", "calculate_route"})

MCP_TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_place",
            "description": (
                "搜索指定城市的旅游景点、公园、博物馆、古迹、商业街等。"
                "返回景点名称、地址、经纬度、类别、评分。每次返回最多 10 条。"
                "在生成任何行程前必须调用此工具获取真实景点数据。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "目标城市或地点，如'北京'、'杭州'",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词，如'故宫'、'西湖'。留空则返回热门景点",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["景点", "公园", "博物馆", "购物", "美食", "古迹", "自然"],
                        "description": "景点类别筛选，留空则不筛选",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": (
                "查询指定城市未来几天的天气（天气状况、温度、风力）。"
                "用于给出穿衣建议和户外活动适宜度判断。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "目标城市",
                    },
                    "days": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 7,
                        "description": "查询未来天数，默认 3",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_route",
            "description": (
                "计算两个地点之间的驾车/步行/骑行距离和预估时间。"
                "用于判断行程中相邻景点的距离是否合理。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "string",
                        "description": "起点名称，如'天安门广场'",
                    },
                    "end": {
                        "type": "string",
                        "description": "终点名称，如'颐和园'",
                    },
                    "city": {
                        "type": "string",
                        "description": "所在城市",
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["driving", "walking", "riding"],
                        "description": "出行方式，默认 driving",
                    },
                },
                "required": ["start", "end", "city"],
            },
        },
    },
]


def is_mcp_tool(name: str) -> bool:
    return name in MCP_TOOL_NAMES


def get_mcp_schemas() -> list[dict]:
    return [dict(s) for s in MCP_TOOL_SCHEMAS]
