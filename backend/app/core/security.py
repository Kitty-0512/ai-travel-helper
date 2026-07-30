"""简易 API Key 鉴权 —— FastAPI 依赖注入"""

from __future__ import annotations

import hmac
import logging

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
logger = logging.getLogger(__name__)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """校验 X-API-Key 请求头，通过则返回 key，否则 401"""
    if not api_key:
        logger.warning("[Auth] missing X-API-Key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-API-Key 请求头",
        )
    if not hmac.compare_digest(api_key, settings.api_secret_key):
        logger.warning("[Auth] invalid API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key 无效",
        )
    return api_key
