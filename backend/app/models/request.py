"""前端请求体模型"""

from pydantic import BaseModel, Field, field_validator


class GenerateRequest(BaseModel):
    """一键生成行程请求"""
    destination: str = Field(..., min_length=1, max_length=50, description="目的地城市")
    days: int = Field(..., ge=1, le=14, description="旅行天数")
    styles: list[str] = Field(default_factory=list, max_length=6, description="旅行风格偏好")

    @field_validator("destination")
    @classmethod
    def trim_destination(cls, v: str) -> str:
        return v.strip()

    @field_validator("styles")
    @classmethod
    def validate_styles(cls, v: list[str]) -> list[str]:
        allowed = {"美食", "历史文化", "自然风光", "购物", "艺术", "冒险"}
        for s in v:
            if s not in allowed:
                raise ValueError(f"不支持的旅行风格: {s}")
        return v


class ChatRequest(BaseModel):
    """多轮修改请求"""
    session_id: str = Field(..., min_length=1, description="会话 ID")
    message: str = Field(..., min_length=1, max_length=500, description="用户修改意见")
