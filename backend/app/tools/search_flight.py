"""机票搜索 —— Mock 返回高质量示例数据"""

import random


# 预设主要城市航线数据
_MOCK_FLIGHTS: dict[str, list[dict]] = {
    "北京": [
        {"flight_no": "MU5101", "airline": "东航", "depart": "07:30", "arrive": "09:50",
         "duration": "2h20m", "price": "¥680-1280", "type": "直达"},
        {"flight_no": "CA1832", "airline": "国航", "depart": "10:15", "arrive": "12:40",
         "duration": "2h25m", "price": "¥720-1560", "type": "直达"},
        {"flight_no": "HO1285", "airline": "吉祥", "depart": "14:00", "arrive": "16:30",
         "duration": "2h30m", "price": "¥540-980", "type": "直达"},
        {"flight_no": "CZ3280", "airline": "南航", "depart": "19:00", "arrive": "21:20",
         "duration": "2h20m", "price": "¥490-860", "type": "直达"},
    ],
    "上海": [
        {"flight_no": "FM9102", "airline": "上航", "depart": "08:00", "arrive": "10:05",
         "duration": "2h05m", "price": "¥560-1020", "type": "直达"},
        {"flight_no": "CA1523", "airline": "国航", "depart": "11:30", "arrive": "13:35",
         "duration": "2h05m", "price": "¥630-1180", "type": "直达"},
        {"flight_no": "MU5160", "airline": "东航", "depart": "16:00", "arrive": "18:05",
         "duration": "2h05m", "price": "¥520-960", "type": "直达"},
    ],
    "广州": [
        {"flight_no": "CZ3501", "airline": "南航", "depart": "09:00", "arrive": "11:30",
         "duration": "2h30m", "price": "¥580-1100", "type": "直达"},
        {"flight_no": "ZH9456", "airline": "深航", "depart": "13:00", "arrive": "15:25",
         "duration": "2h25m", "price": "¥490-890", "type": "直达"},
        {"flight_no": "CA4308", "airline": "国航", "depart": "18:30", "arrive": "20:55",
         "duration": "2h25m", "price": "¥610-1320", "type": "直达"},
    ],
    "成都": [
        {"flight_no": "3U8701", "airline": "川航", "depart": "07:00", "arrive": "09:30",
         "duration": "2h30m", "price": "¥520-960", "type": "直达"},
        {"flight_no": "CA4102", "airline": "国航", "depart": "12:00", "arrive": "14:30",
         "duration": "2h30m", "price": "¥580-1050", "type": "直达"},
        {"flight_no": "MU5420", "airline": "东航", "depart": "17:00", "arrive": "19:30",
         "duration": "2h30m", "price": "¥460-820", "type": "直达"},
    ],
}

_DEFAULT_FLIGHTS: list[dict] = [
    {"flight_no": "CZ3001", "airline": "南航", "depart": "08:30", "arrive": "11:00",
     "duration": "2h30m", "price": "¥550-1050", "type": "直达"},
    {"flight_no": "MU2001", "airline": "东航", "depart": "13:00", "arrive": "15:30",
     "duration": "2h30m", "price": "¥590-1150", "type": "直达"},
    {"flight_no": "CA1001", "airline": "国航", "depart": "18:00", "arrive": "20:30",
     "duration": "2h30m", "price": "¥480-920", "type": "直达"},
]


async def search_flights(
    from_city: str,
    to_city: str,
    date: str = "",
) -> dict:
    """
    搜索机票（Mock 数据）。
    按目的地城市返回预设的高质量示例数据。
    """
    flights = _MOCK_FLIGHTS.get(to_city, _DEFAULT_FLIGHTS)

    # 加点随机价格波动，看起来更真实
    result = []
    for f in flights:
        price_low = int(f["price"].split("-")[0].replace("¥", "").replace(",", ""))
        price_high = int(f["price"].split("-")[1].replace("¥", "").replace(",", "")) if "-" in f["price"] else price_low
        jitter = random.randint(-30, 50)
        result.append({
            **f,
            "price": f"¥{price_low + jitter}-{price_high + jitter}",
        })

    return {
        "flights": result,
        "from_city": from_city,
        "to_city": to_city,
        "date": date or "未指定日期",
        "note": "机票价格为经济舱参考价（Mock 数据），实际价格请以购票平台为准",
    }
