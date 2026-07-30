"""Session history API — list, get, delete past trip planning sessions."""

from fastapi import APIRouter, Security, Depends
from pydantic import BaseModel

from app.core.security import verify_api_key
from app.core.limiter import default_limiter
from app.core.user_id import require_user_id
from app.session.repository import session_repo

router = APIRouter()


# ── Response models ──────────────────────────────────────────

class SessionSummary(BaseModel):
    session_id: str
    destination: str
    days: int
    styles: list[str]
    created_at: str


class SessionListResponse(BaseModel):
    user_id: str
    sessions: list[SessionSummary]


class SessionDetail(BaseModel):
    session_id: str
    destination: str
    days: int
    styles: list[str]
    itinerary: dict | None = None
    places_detail: list[dict] | None = None
    markdown_text: str = ""
    created_at: str


class DeleteResponse(BaseModel):
    session_id: str
    deleted: bool


# ── Endpoints ────────────────────────────────────────────────


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    _api_key: str = Security(verify_api_key),
    _rl: None = Depends(default_limiter),
    user_id: str = Depends(require_user_id),
):
    """List all past trip planning sessions for the current user."""
    rows = await session_repo.list_by_user(user_id)
    return SessionListResponse(
        user_id=user_id,
        sessions=[SessionSummary(**row) for row in rows],
    )


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: str,
    _api_key: str = Security(verify_api_key),
    _rl: None = Depends(default_limiter),
    user_id: str = Depends(require_user_id),
):
    """Get full session detail including itinerary and places."""
    detail = await session_repo.get(session_id)
    if detail is None:
        # Return empty to avoid 404 messing with EventSource
        return SessionDetail(
            session_id=session_id,
            destination="",
            days=0,
            styles=[],
            created_at="",
        )
    return SessionDetail(**detail)


@router.delete("/{session_id}", response_model=DeleteResponse)
async def delete_session(
    session_id: str,
    _api_key: str = Security(verify_api_key),
    _rl: None = Depends(default_limiter),
    user_id: str = Depends(require_user_id),
):
    """Delete a past session."""
    ok = await session_repo.delete(session_id, user_id)
    return DeleteResponse(session_id=session_id, deleted=ok)
