"""健康检查端点"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.memory import memory_manager
from app.mcp import mcp_client
from app.trace import trace_manager

router = APIRouter()


@router.get("/health")
async def health_check():
    return await ready_check()


@router.get("/health/live")
async def live_check():
    return {"status": "ok", "service": "ai-travel-helper"}


@router.get("/health/ready")
async def ready_check():
    checks = {
        "memory": {"enabled": settings.memory_enabled, "ready": memory_manager.available},
        "trace": {"enabled": settings.trace_enabled, "ready": trace_manager.available},
        "mcp": {"enabled": settings.mcp_enabled, "ready": mcp_client.connected},
    }
    failures: list[str] = []
    if settings.memory_enabled and settings.is_production and not checks["memory"]["ready"]:
        failures.append("memory")
    if settings.trace_enabled and settings.is_production and not checks["trace"]["ready"]:
        failures.append("trace")
    if settings.mcp_enabled and not checks["mcp"]["ready"]:
        failures.append("mcp")

    payload = {
        "status": "ok" if not failures else "degraded",
        "service": "ai-travel-helper",
        "checks": checks,
    }
    if failures:
        return JSONResponse(status_code=503, content=payload)
    return payload
