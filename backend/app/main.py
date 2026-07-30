"""FastAPI 应用入口"""

import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.routers import agent, agent_chat, health, memory, sessions, trace
from app.session.store import session_store
from app.session.repository import session_repo
from app.memory import memory_manager
from app.mcp import mcp_client
from app.trace import trace_manager

setup_logging(settings.env)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化，关闭时清理"""
    await memory_manager.startup()
    await trace_manager.startup()
    await session_repo.connect()
    await mcp_client.connect()
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await mcp_client.disconnect()
    await session_repo.close()
    await trace_manager.shutdown()
    await memory_manager.shutdown()


async def _periodic_cleanup(interval: int = 600):
    """每 10 分钟清理一次过期会话"""
    while True:
        await asyncio.sleep(interval)
        try:
            count = session_store.cleanup_expired()
            if count > 0:
                logger.info("[Cleanup] cleaned %s expired sessions", count)
        except Exception as e:
            logger.warning("[Cleanup] error: %s", e)


app = FastAPI(
    title="AI Travel Helper API",
    description="AI travel agent backend",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request, call_next):
    request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:12]
    request.state.request_id = request_id
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("[Request] unhandled request_id=%s path=%s", request_id, request.url.path)
        raise
    duration_ms = round((time.perf_counter() - start) * 1000)
    response.headers["X-Request-Id"] = request_id
    logger.info(
        "[Request] id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response

# ── Exception handlers ──
register_exception_handlers(app)

# ── Routes ──
app.include_router(agent.router, prefix="/api/agent", tags=["Agent"])
app.include_router(agent_chat.router, prefix="/api/agent", tags=["Agent Chat"])
app.include_router(memory.router, prefix="/api/memory", tags=["Memory"])
app.include_router(trace.router, prefix="/api/trace", tags=["Trace"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(health.router, prefix="/api", tags=["Health"])


# ── 前端静态资源托管（单服务部署）──
_static_dir = Path(settings.static_dir or "static")

if _static_dir.is_dir():
    _static_root = _static_dir.resolve()
    _index_file = _static_root / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        """命中真实文件则直接返回，否则回退 index.html 交给前端路由处理。"""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        candidate = (_static_root / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_static_root):
            return FileResponse(candidate)
        return FileResponse(_index_file)

    logger.info("前端静态资源: 已挂载 %s", _static_root)
else:
    @app.get("/")
    async def root():
        return {"message": "AI Travel Helper API", "docs": "/docs"}

    logger.info("前端静态资源: 未找到 %s，仅提供 API", _static_dir)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.env == "development",
    )
