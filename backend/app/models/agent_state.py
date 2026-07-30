"""Agent 内部状态"""

from dataclasses import dataclass, field
import time


@dataclass
class AgentState:
    """Agent 会话状态 —— 存于 session store"""
    session_id: str
    messages: list[dict] = field(default_factory=list)
    destination: str = ""
    days: int = 1
    styles: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    itinerary: dict | None = None  # 上次提取的行程数据，多轮续聊时用于合并

    def touch(self):
        self.last_access = time.time()

    def is_expired(self, ttl: int = 3600) -> bool:
        return time.time() - self.last_access > ttl
