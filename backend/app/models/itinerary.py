"""行程数据结构 —— 前后端共享契约"""

from pydantic import BaseModel, Field


class DayData(BaseModel):
    day: int
    morning: str = ""
    afternoon: str = ""
    evening: str = ""


class PlaceInfo(BaseModel):
    """高德 POI 返回的景点信息"""
    name: str
    address: str = ""
    lng: float
    lat: float
    category: str = ""
    rating: str = ""


class ItineraryData(BaseModel):
    """最终结构化行程 —— 前端渲染地图和卡片用"""
    days: list[DayData]
    allPlaces: list[str]  # 去重后的景点名称列表


class FinalItineraryResponse(BaseModel):
    """生成完成后返回的完整数据"""
    itinerary: ItineraryData
    places_detail: list[PlaceInfo] = Field(default_factory=list)  # 带坐标的景点详情
    session_id: str
    destination: str
    days: int
