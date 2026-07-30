"""酒店搜索 —— Mock 返回高质量示例数据"""

import random


_MOCK_HOTELS: dict[str, list[dict]] = {
    "北京": [
        {"name": "北京王府井希尔顿酒店", "area": "王府井", "rating": 4.8,
         "price_low": 680, "price_high": 1200, "highlight": "步行 5 分钟到故宫"},
        {"name": "北京前门建国饭店", "area": "前门", "rating": 4.5,
         "price_low": 420, "price_high": 780, "highlight": "老北京四合院风格"},
        {"name": "北京三里屯洲际酒店", "area": "三里屯", "rating": 4.7,
         "price_low": 880, "price_high": 1500, "highlight": "毗邻太古里商圈"},
        {"name": "北京南锣鼓巷漫心酒店", "area": "南锣鼓巷", "rating": 4.6,
         "price_low": 350, "price_high": 650, "highlight": "胡同文化体验"},
        {"name": "北京国贸大酒店", "area": "国贸", "rating": 4.9,
         "price_low": 1200, "price_high": 2500, "highlight": "CBD 天际线景观"},
    ],
    "上海": [
        {"name": "上海外滩华尔道夫酒店", "area": "外滩", "rating": 4.9,
         "price_low": 1500, "price_high": 3000, "highlight": "外滩江景"},
        {"name": "上海静安香格里拉", "area": "静安寺", "rating": 4.8,
         "price_low": 900, "price_high": 1800, "highlight": "毗邻静安寺商圈"},
        {"name": "上海新天地朗廷酒店", "area": "新天地", "rating": 4.7,
         "price_low": 800, "price_high": 1600, "highlight": "石库门风情"},
        {"name": "上海南京路全季酒店", "area": "南京路", "rating": 4.3,
         "price_low": 280, "price_high": 520, "highlight": "步行街核心位置"},
    ],
    "杭州": [
        {"name": "杭州西湖国宾馆", "area": "西湖", "rating": 4.9,
         "price_low": 1200, "price_high": 2200, "highlight": "西湖畔私家园林"},
        {"name": "杭州法云安缦", "area": "灵隐", "rating": 4.9,
         "price_low": 3000, "price_high": 6000, "highlight": "千年古村落改造"},
        {"name": "杭州城中香格里拉", "area": "武林广场", "rating": 4.7,
         "price_low": 700, "price_high": 1300, "highlight": "市中心交通便利"},
        {"name": "杭州西湖亚朵酒店", "area": "湖滨", "rating": 4.5,
         "price_low": 350, "price_high": 620, "highlight": "步行至断桥 10 分钟"},
    ],
}

_DEFAULT_HOTELS: list[dict] = [
    {"name": "城市中心万豪酒店", "area": "市中心", "rating": 4.7,
     "price_low": 600, "price_high": 1200, "highlight": "位置优越，交通便利"},
    {"name": "城市花园亚朵酒店", "area": "市中心", "rating": 4.5,
     "price_low": 320, "price_high": 580, "highlight": "性价比高，干净舒适"},
    {"name": "城市商务希尔顿", "area": "CBD", "rating": 4.8,
     "price_low": 850, "price_high": 1700, "highlight": "商务出行首选"},
]

_BUDGET_MAP = {
    "经济": (0, 400),
    "舒适": (300, 900),
    "高档": (700, 1800),
    "奢华": (1500, 4000),
}


async def search_hotels(
    city: str,
    area: str = "",
    budget: str = "",
) -> dict:
    """
    搜索酒店（Mock 数据）。
    按城市返回预设示例，支持预算筛选。
    """
    hotels = _MOCK_HOTELS.get(city, _DEFAULT_HOTELS)

    # 预算筛选
    if budget and budget in _BUDGET_MAP:
        lo, hi = _BUDGET_MAP[budget]
        hotels = [h for h in hotels if h["price_low"] >= lo and h["price_high"] <= hi]
        if not hotels:
            hotels = _MOCK_HOTELS.get(city, _DEFAULT_HOTELS)  # fallback

    # 区域筛选
    if area:
        hotels = [h for h in hotels if area in h.get("area", "") or area in h.get("name", "")]
        if not hotels:
            hotels = _MOCK_HOTELS.get(city, _DEFAULT_HOTELS)

    # 加随机价格波动
    result = []
    for h in hotels:
        jitter = random.randint(-30, 60)
        result.append({
            "name": h["name"],
            "area": h["area"],
            "rating": h["rating"],
            "price": f"¥{h['price_low'] + jitter}-{h['price_high'] + jitter}/晚",
            "highlight": h["highlight"],
        })

    return {
        "hotels": result,
        "city": city,
        "area": area or "未指定区域",
        "budget": budget or "未指定预算",
        "total": len(result),
        "note": "酒店价格随季节波动，建议提前预订（Mock 数据仅供参考）",
    }
