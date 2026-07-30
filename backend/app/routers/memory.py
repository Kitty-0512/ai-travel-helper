"""Memory HTTP API — GET/DELETE /api/memory"""

from fastapi import APIRouter, Security, Depends
from pydantic import BaseModel
from typing import Any

from app.core.security import verify_api_key
from app.core.limiter import default_limiter
from app.core.user_id import require_user_id
from app.memory import memory_manager

router = APIRouter()


class MemoryItem(BaseModel):
    id: str
    memory_type: str
    content: str
    structured: dict[str, Any]
    source_session_id: str | None = None
    created_time: str | None = None


class MemoryListResponse(BaseModel):
    user_id: str
    available: bool
    profile: dict[str, Any]
    memories: list[MemoryItem]


class MemoryDeleteResponse(BaseModel):
    user_id: str
    deleted: int


@router.get("", response_model=MemoryListResponse)
async def list_memory(
    _api_key: str = Security(verify_api_key),
    _rl: None = Depends(default_limiter),
    user_id: str = Depends(require_user_id),
):
    profile = await memory_manager.get_profile(user_id)
    records = await memory_manager.list_memories(user_id)
    return MemoryListResponse(
        user_id=user_id,
        available=memory_manager.available,
        profile=profile.model_dump(),
        memories=[
            MemoryItem(
                id=str(r.id),
                memory_type=r.memory_type,
                content=r.content,
                structured=r.structured,
                source_session_id=r.source_session_id,
                created_time=r.created_time.isoformat() if r.created_time else None,
            )
            for r in records
        ],
    )


@router.delete("", response_model=MemoryDeleteResponse)
async def delete_all_memory(
    _api_key: str = Security(verify_api_key),
    _rl: None = Depends(default_limiter),
    user_id: str = Depends(require_user_id),
):
    deleted = await memory_manager.delete_memories(user_id)
    return MemoryDeleteResponse(user_id=user_id, deleted=deleted)


@router.delete("/{memory_id}", response_model=MemoryDeleteResponse)
async def delete_one_memory(
    memory_id: str,
    _api_key: str = Security(verify_api_key),
    _rl: None = Depends(default_limiter),
    user_id: str = Depends(require_user_id),
):
    ok = await memory_manager.delete_memory(user_id, memory_id)
    return MemoryDeleteResponse(user_id=user_id, deleted=1 if ok else 0)
