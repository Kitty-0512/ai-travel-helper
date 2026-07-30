"""Agent SSE 端点 —— POST /api/agent/generate"""

from contextlib import suppress

from fastapi import APIRouter, Security, Request, Depends
from sse_starlette.sse import EventSourceResponse

from app.core.security import verify_api_key
from app.core.limiter import generate_limiter
from app.core.exceptions import InvalidRequestError, AppError
from app.core.user_id import optional_user_id
from app.models.request import GenerateRequest
from app.agents.loop import run_agent

router = APIRouter()


# ── OPTIONS 预检 ──
@router.options("/generate")
@router.options("/chat")
async def options_preflight(request: Request):
    return {}


@router.post("/generate")
async def generate_travel_plan(
    request: Request,
    req: GenerateRequest,
    _api_key: str = Security(verify_api_key),
    _rl: None = Depends(generate_limiter),  # 10 req/min per IP
    user_id: str | None = Depends(optional_user_id),
):
    """
    一键生成旅行行程（SSE 流式）。

    事件类型: agent_think | tool_call | tool_result | chunk | itinerary_json | done | error
    """
    if not req.destination:
        raise InvalidRequestError("目的地不能为空")
    if req.days < 1 or req.days > 14:
        raise InvalidRequestError("天数必须在 1-14 之间")

    async def event_generator():
        agen = run_agent(
            destination=req.destination,
            days=req.days,
            styles=req.styles,
            user_id=user_id,
        )
        try:
            async for event in agen:
                if await request.is_disconnected():
                    break
                yield {
                    "event": event.type,
                    "data": event.data,
                    "id": str(event.id),
                }
        finally:
            with suppress(Exception):
                await agen.aclose()

    # 使用 FastAPI 原生的 streaming 方式——EventSourceResponse
    # 注意：sse-starlette 的 EventSourceResponse 期望一个 async generator
    return EventSourceResponse(
        _sse_wrapper(event_generator()),
        media_type="text/event-stream",
        ping=15,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _sse_wrapper(agen):
    """确保事件以标准 SSE 格式输出"""
    async for item in agen:
        data = item["data"]
        if isinstance(data, (dict, list)):
            import orjson
            data_str = orjson.dumps(data, default=str).decode("utf-8")
        else:
            data_str = str(data) if data is not None else "{}"

        event = item.get("event", "message")
        ev_id = item.get("id", "0")

        yield {
            "event": event,
            "data": data_str,
            "id": str(ev_id),
        }
