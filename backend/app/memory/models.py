"""Memory data models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ExtractedPreferences(BaseModel):
    style: str | None = None
    interests: list[str] = Field(default_factory=list)
    dislike: list[str] = Field(default_factory=list)
    budget: str | None = None
    transport: str | None = None
    constraints: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            [
                self.style,
                self.interests,
                self.dislike,
                self.budget,
                self.transport,
                self.constraints,
            ]
        )


class UserProfile(BaseModel):
    style: str | None = None
    interests: list[str] = Field(default_factory=list)
    dislike: list[str] = Field(default_factory=list)
    budget: str | None = None
    transport: str | None = None
    constraints: list[str] = Field(default_factory=list)
    updated_at: float | None = None

    def to_prompt_text(self) -> str:
        likes: list[str] = []
        if self.style:
            likes.append(self.style)
        likes.extend(self.interests)
        avoid = list(self.dislike)
        parts: list[str] = []
        if likes:
            parts.append(f"喜欢：{'、'.join(dict.fromkeys(likes))}")
        if avoid:
            parts.append(f"避免：{'、'.join(dict.fromkeys(avoid))}")
        if self.budget:
            parts.append(f"预算：{self.budget}")
        if self.transport:
            parts.append(f"出行方式：{self.transport}")
        if self.constraints:
            parts.append(f"禁忌/约束：{'、'.join(self.constraints)}")
        if not parts:
            return ""
        return "【用户长期偏好】" + "；".join(parts)

    def merge_extracted(self, pref: ExtractedPreferences) -> "UserProfile":
        if pref.style:
            self.style = pref.style
        if pref.interests:
            self.interests = list(dict.fromkeys([*self.interests, *pref.interests]))
        if pref.dislike:
            self.dislike = list(dict.fromkeys([*self.dislike, *pref.dislike]))
        if pref.budget:
            self.budget = pref.budget
        if pref.transport:
            self.transport = pref.transport
        if pref.constraints:
            self.constraints = list(dict.fromkeys([*self.constraints, *pref.constraints]))
        return self


class MemoryRecord(BaseModel):
    id: UUID | str
    user_id: str
    memory_type: str
    content: str
    structured: dict[str, Any] = Field(default_factory=dict)
    source_session_id: str | None = None
    created_time: datetime | None = None
    updated_time: datetime | None = None
    is_active: bool = True
