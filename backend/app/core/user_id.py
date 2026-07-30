"""Optional X-User-Id extraction for long-term memory."""

import re

from fastapi import Header, HTTPException, status

USER_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


async def optional_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str | None:
    if x_user_id is None:
        return None
    value = x_user_id.strip()
    if not value:
        return None
    if len(value) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id 过长",
        )
    if not USER_ID_RE.fullmatch(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-Id 仅支持字母、数字、下划线和短横线",
        )
    return value


async def require_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    value = await optional_user_id(x_user_id)
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少 X-User-Id 请求头",
        )
    return value
