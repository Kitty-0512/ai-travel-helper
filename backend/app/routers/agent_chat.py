"""多轮修改端点 —— POST /api/agent/chat"""

from contextlib import suppress

from fastapi import APIRouter, Security, Request, Depends
from sse_starlette.sse import EventSourceResponse
import orjson

from app.core.security import verify_api_key
from app.core.limiter import chat_limiter
from app.core.exceptions import InvalidRequestError
from app.core.user_id import optional_user_id
from app.models.request import ChatRequest
from app.agents.loop import run_agent
from app.session.store import session_store
from app.session.repository import session_repo

router = APIRouter()


@router.post("/chat")
async def continue_chat(
    request: Request,
    req: ChatRequest,
    _api_key: str = Security(verify_api_key),
    _rl: None = Depends(chat_limiter),  # 15 req/min per IP
    user_id: str | None = Depends(optional_user_id),
):
    """
    多轮修改：在已有行程上进行修改。

    需要传入 session_id（从 /generate 的 done 事件中获取）。
    """
    state = session_store.get(req.session_id)

    # In-memory session expired or backend restarted — try restoring from PG
    if state is None and session_repo.ready:
        full = await session_repo.get_full(req.session_id)
        if full is not None:
            state = session_store.create(
                destination=full["destination"],
                days=full["days"],
                styles=full.get("styles", []),
            )
            state.session_id = full["session_id"]
            state.messages = full.get("messages", [])
            if full.get("itinerary"):
                state.itinerary = full["itinerary"]
            session_store.set(state.session_id, state)

    if state is None:
        raise InvalidRequestError("会话不存在或已过期，请重新生成行程")

    async def event_generator():
        agen = run_agent(
            destination=state.destination,
            days=state.days,
            styles=state.styles,
            previous_messages=state.messages,
            user_feedback=req.message,
            session_id=state.session_id,
            user_id=user_id,
        )
        try:
            async for event in agen:
                if await request.is_disconnected():
                    break
                yield {
                    "event": event.type,
                    "data": (
                        orjson.dumps(event.data, default=str).decode("utf-8")
                        if isinstance(event.data, (dict, list))
                        else str(event.data) if event.data is not None else "{}"
                    ),
                    "id": str(event.id),
                }
        finally:
            with suppress(Exception):
                await agen.aclose()

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
