"""Redis + PostgreSQL storage for agent memory (with in-process fallback)."""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from redis import asyncio as aioredis

from app.core.config import settings
from app.memory.models import MemoryRecord, UserProfile

logger = logging.getLogger(__name__)


def _profile_key(user_id: str) -> str:
    return f"memory:profile:{user_id}"


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"


def _cosine_distance(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return 1.0 - (dot / (na * nb))


class MemoryStorage:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._pool: asyncpg.Pool | None = None
        self._ready = False
        self._backend: str = "none"  # redis_pg | memory | none
        # In-process fallback
        self._profiles: dict[str, UserProfile] = {}
        self._rows: list[dict[str, Any]] = []

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def backend(self) -> str:
        return self._backend

    async def connect(self) -> None:
        if not settings.memory_enabled:
            logger.info("[Memory] disabled by config")
            return
        try:
            self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
            await self._redis.ping()
            self._pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5)
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT 1")
            self._ready = True
            self._backend = "redis_pg"
            logger.info("[Memory] Redis + PostgreSQL connected")
            return
        except Exception as e:
            logger.warning("[Memory] Redis/PG unavailable: %s", e)
            await self._close_remote()

        if settings.memory_fallback_inprocess and not settings.is_production:
            self._ready = True
            self._backend = "memory"
            logger.warning("[Memory] using in-process fallback (non-durable)")
        else:
            self._ready = False
            self._backend = "none"
            logger.warning("[Memory] storage unavailable, agent will skip memory")

    async def _close_remote(self) -> None:
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:
                pass
            self._redis = None
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:
                pass
            self._pool = None

    async def close(self) -> None:
        await self._close_remote()
        self._profiles.clear()
        self._rows.clear()
        self._ready = False
        self._backend = "none"

    # ── Profile ──

    async def get_profile(self, user_id: str) -> UserProfile | None:
        if not self._ready:
            return None
        if self._backend == "memory":
            return self._profiles.get(user_id)
        if self._redis is None:
            return None
        try:
            raw = await self._redis.get(_profile_key(user_id))
            if not raw:
                return None
            return UserProfile.model_validate(json.loads(raw))
        except Exception as e:
            logger.warning("[Memory] redis get failed: %s", e)
            return None

    async def set_profile(self, user_id: str, profile: UserProfile) -> None:
        if not self._ready:
            return
        profile.updated_at = time.time()
        if self._backend == "memory":
            self._profiles[user_id] = profile
            return
        if self._redis is None:
            return
        try:
            await self._redis.set(
                _profile_key(user_id),
                profile.model_dump_json(),
                ex=settings.memory_redis_ttl_seconds,
            )
        except Exception as e:
            logger.warning("[Memory] redis set failed: %s", e)

    async def delete_profile(self, user_id: str) -> None:
        if not self._ready:
            return
        if self._backend == "memory":
            self._profiles.pop(user_id, None)
            return
        if self._redis is None:
            return
        try:
            await self._redis.delete(_profile_key(user_id))
        except Exception as e:
            logger.warning("[Memory] redis delete failed: %s", e)

    # ── Rows ──

    async def insert_memory(
        self,
        user_id: str,
        memory_type: str,
        content: str,
        structured: dict[str, Any],
        embedding: list[float] | None = None,
        source_session_id: str | None = None,
    ) -> MemoryRecord | None:
        if not self._ready:
            return None

        if self._backend == "memory":
            now = datetime.now(timezone.utc)
            row = {
                "id": uuid4(),
                "user_id": user_id,
                "memory_type": memory_type,
                "content": content,
                "structured": structured,
                "embedding": embedding,
                "source_session_id": source_session_id,
                "created_time": now,
                "updated_time": now,
                "is_active": True,
            }
            self._rows.append(row)
            return MemoryRecord(
                id=row["id"],
                user_id=user_id,
                memory_type=memory_type,
                content=content,
                structured=structured,
                source_session_id=source_session_id,
                created_time=now,
                updated_time=now,
                is_active=True,
            )

        if self._pool is None:
            return None
        try:
            emb_lit = _vector_literal(embedding) if embedding else None
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    INSERT INTO user_memory
                        (user_id, memory_type, content, structured, embedding, source_session_id)
                    VALUES
                        ($1, $2, $3, $4::jsonb, $5::vector, $6)
                    RETURNING id, user_id, memory_type, content, structured,
                              source_session_id, created_time, updated_time, is_active
                    """,
                    user_id,
                    memory_type,
                    content,
                    json.dumps(structured, ensure_ascii=False),
                    emb_lit,
                    source_session_id,
                )
            return _row_to_record(row)
        except Exception as e:
            logger.warning("[Memory] insert failed: %s", e)
            return None

    async def list_memories(self, user_id: str, limit: int = 100) -> list[MemoryRecord]:
        if not self._ready:
            return []
        if self._backend == "memory":
            rows = [
                r for r in self._rows
                if r["user_id"] == user_id and r["is_active"]
            ]
            rows.sort(key=lambda r: r["created_time"], reverse=True)
            return [
                MemoryRecord(
                    id=r["id"],
                    user_id=r["user_id"],
                    memory_type=r["memory_type"],
                    content=r["content"],
                    structured=r["structured"],
                    source_session_id=r["source_session_id"],
                    created_time=r["created_time"],
                    updated_time=r["updated_time"],
                    is_active=r["is_active"],
                )
                for r in rows[:limit]
            ]

        if self._pool is None:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, memory_type, content, structured,
                           source_session_id, created_time, updated_time, is_active
                    FROM user_memory
                    WHERE user_id = $1 AND is_active = TRUE
                    ORDER BY created_time DESC
                    LIMIT $2
                    """,
                    user_id,
                    limit,
                )
            return [_row_to_record(r) for r in rows]
        except Exception as e:
            logger.warning("[Memory] list failed: %s", e)
            return []

    async def soft_delete_all(self, user_id: str) -> int:
        if not self._ready:
            return 0
        if self._backend == "memory":
            count = 0
            now = datetime.now(timezone.utc)
            for r in self._rows:
                if r["user_id"] == user_id and r["is_active"]:
                    r["is_active"] = False
                    r["updated_time"] = now
                    count += 1
            return count

        if self._pool is None:
            return 0
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE user_memory
                    SET is_active = FALSE, updated_time = NOW()
                    WHERE user_id = $1 AND is_active = TRUE
                    """,
                    user_id,
                )
            return int(result.split()[-1]) if result else 0
        except Exception as e:
            logger.warning("[Memory] soft_delete_all failed: %s", e)
            return 0

    async def soft_delete_one(self, user_id: str, memory_id: str | UUID) -> bool:
        if not self._ready:
            return False
        mid = str(memory_id)
        if self._backend == "memory":
            for r in self._rows:
                if r["user_id"] == user_id and str(r["id"]) == mid and r["is_active"]:
                    r["is_active"] = False
                    r["updated_time"] = datetime.now(timezone.utc)
                    return True
            return False

        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as conn:
                result = await conn.execute(
                    """
                    UPDATE user_memory
                    SET is_active = FALSE, updated_time = NOW()
                    WHERE user_id = $1 AND id = $2::uuid AND is_active = TRUE
                    """,
                    user_id,
                    mid,
                )
            return result.endswith("1")
        except Exception as e:
            logger.warning("[Memory] soft_delete_one failed: %s", e)
            return False

    async def search_similar(
        self,
        user_id: str,
        query_embedding: list[float],
        top_k: int | None = None,
    ) -> list[MemoryRecord]:
        if not self._ready:
            return []
        k = top_k or settings.memory_top_k

        if self._backend == "memory":
            scored: list[tuple[float, dict[str, Any]]] = []
            for r in self._rows:
                if r["user_id"] != user_id or not r["is_active"]:
                    continue
                emb = r.get("embedding")
                dist = _cosine_distance(query_embedding, emb) if emb else 1.0
                scored.append((dist, r))
            scored.sort(key=lambda x: x[0])
            return [
                MemoryRecord(
                    id=r["id"],
                    user_id=r["user_id"],
                    memory_type=r["memory_type"],
                    content=r["content"],
                    structured=r["structured"],
                    source_session_id=r["source_session_id"],
                    created_time=r["created_time"],
                    updated_time=r["updated_time"],
                    is_active=r["is_active"],
                )
                for _, r in scored[:k]
            ]

        if self._pool is None:
            return []
        try:
            emb_lit = _vector_literal(query_embedding)
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, user_id, memory_type, content, structured,
                           source_session_id, created_time, updated_time, is_active
                    FROM user_memory
                    WHERE user_id = $1 AND is_active = TRUE AND embedding IS NOT NULL
                    ORDER BY embedding <=> $2::vector
                    LIMIT $3
                    """,
                    user_id,
                    emb_lit,
                    k,
                )
            return [_row_to_record(r) for r in rows]
        except Exception as e:
            logger.warning("[Memory] vector search failed, fallback to recent: %s", e)
            return await self.list_memories(user_id, limit=k)


def _row_to_record(row: asyncpg.Record) -> MemoryRecord:
    structured = row["structured"]
    if isinstance(structured, str):
        structured = json.loads(structured)
    return MemoryRecord(
        id=row["id"],
        user_id=row["user_id"],
        memory_type=row["memory_type"],
        content=row["content"],
        structured=structured or {},
        source_session_id=row["source_session_id"],
        created_time=row["created_time"],
        updated_time=row["updated_time"],
        is_active=row["is_active"],
    )


storage = MemoryStorage()
