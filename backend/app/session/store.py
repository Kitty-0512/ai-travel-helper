"""会话存储 —— MVP 用内存 dict + TTL，后续可换 Redis"""

import time
import uuid
from typing import Protocol

from app.models.agent_state import AgentState


class SessionStore(Protocol):
    """会话存储接口 —— 后续 RedisSessionStore 实现同一接口即可"""

    def get(self, session_id: str) -> AgentState | None: ...
    def set(self, session_id: str, state: AgentState) -> None: ...
    def delete(self, session_id: str) -> None: ...
    def cleanup_expired(self) -> int: ...  # 返回清理数量


class MemorySessionStore:
    """基于内存 dict 的会话存储"""

    def __init__(self, default_ttl: int = 3600):
        self._store: dict[str, AgentState] = {}
        self._default_ttl = default_ttl

    def get(self, session_id: str) -> AgentState | None:
        state = self._store.get(session_id)
        if state is None:
            return None
        if state.is_expired(self._default_ttl):
            del self._store[session_id]
            return None
        state.touch()
        return state

    def set(self, session_id: str, state: AgentState) -> None:
        state.touch()
        self._store[session_id] = state

    def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    def create(self, destination: str, days: int, styles: list[str]) -> AgentState:
        """新建一个会话"""
        session_id = str(uuid.uuid4())[:8]  # 短 ID，够用
        state = AgentState(
            session_id=session_id,
            destination=destination,
            days=days,
            styles=styles,
        )
        self.set(session_id, state)
        return state

    def cleanup_expired(self) -> int:
        """清理过期会话"""
        expired = [
            sid for sid, state in self._store.items()
            if state.is_expired(self._default_ttl)
        ]
        for sid in expired:
            del self._store[sid]
        return len(expired)


# 全局单例
session_store = MemorySessionStore()
