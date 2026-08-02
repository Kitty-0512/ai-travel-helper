"""Redis-first rate limiter with in-memory dev fallback."""

import logging
import time
from collections import defaultdict

from fastapi import HTTPException, Request, Response
from redis import asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)


def _parse_rate(spec: str) -> tuple[int, int]:
    amount, _, unit = spec.partition("/")
    calls = int(amount.strip())
    unit = unit.strip().lower()
    if unit in {"minute", "min"}:
        return calls, 60
    if unit in {"hour", "hr"}:
        return calls, 3600
    return calls, 60


class SimpleRateLimiter:
    """Redis-backed rate limiter with local fallback.

    NOTE: do not use `from __future__ import annotations` in this module.
    FastAPI must see runtime Request/Response types to inject them via Depends.
    """

    def __init__(self, spec: str = "10/minute", scope: str = "default"):
        self.max_calls, self.window = _parse_rate(spec)
        self.scope = scope
        self._store: dict[str, list[float]] = defaultdict(list)
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis | None:
        if settings.rate_limit_backend != "redis":
            return None
        if self._redis is None:
            try:
                self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
                await self._redis.ping()
            except Exception as exc:
                logger.warning("[RateLimit] redis unavailable, fallback to memory: %s", exc)
                self._redis = None
        return self._redis

    async def __call__(self, request: Request, response: Response) -> None:
        if not settings.rate_limit_enabled:
            return
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")
        now = time.time()
        redis_client = await self._get_redis()

        if redis_client is not None:
            try:
                key = f"rl:{self.scope}:{ip}"
                current = await redis_client.incr(key)
                if current == 1:
                    await redis_client.expire(key, self.window)
                ttl = await redis_client.ttl(key)
                remaining = max(self.max_calls - current, 0)
                response.headers["X-RateLimit-Limit"] = str(self.max_calls)
                response.headers["X-RateLimit-Remaining"] = str(remaining)
                response.headers["X-RateLimit-Reset"] = str(max(ttl, 0))
                if current > self.max_calls:
                    raise HTTPException(
                        status_code=429,
                        detail={"type": "error", "code": "RATE_LIMITED", "message": "request too frequent, try again later"},
                    )
                return
            except Exception as exc:
                logger.warning("[RateLimit] redis op failed, fallback to memory: %s", exc)
                self._redis = None

        self._store[ip] = [t for t in self._store[ip] if now - t < self.window]
        remaining = max(self.max_calls - len(self._store[ip]) - 1, 0)
        response.headers["X-RateLimit-Limit"] = str(self.max_calls)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(self.window)
        if len(self._store[ip]) >= self.max_calls:
            raise HTTPException(
                status_code=429,
                detail={"type": "error", "code": "RATE_LIMITED", "message": "request too frequent, try again later"},
            )
        self._store[ip].append(now)


# 不同端点的限流器
generate_limiter = SimpleRateLimiter(settings.rate_limit_generate, "generate")
chat_limiter = SimpleRateLimiter(settings.rate_limit_chat, "chat")
default_limiter = SimpleRateLimiter(settings.rate_limit_default, "default")
