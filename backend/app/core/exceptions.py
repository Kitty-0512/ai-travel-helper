"""统一异常处理"""

from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """业务异常基类"""

    def __init__(self, code: str, message: str, status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code


class LLMTimeoutError(AppError):
    def __init__(self):
        super().__init__("LLM_TIMEOUT", "AI 响应超时，请稍后重试", 502)


class LLMAPIError(AppError):
    def __init__(self, detail: str = ""):
        super().__init__("LLM_API_ERROR", f"AI 服务暂时不可用 {detail}".strip(), 502)


class ToolAllFailedError(AppError):
    def __init__(self):
        super().__init__("TOOL_ALL_FAILED", "地点搜索暂时不可用，请稍后重试", 502)


class InvalidRequestError(AppError):
    def __init__(self, detail: str = ""):
        super().__init__("INVALID_REQUEST", detail or "请检查请求参数", 400)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "[AppError] path=%s request_id=%s code=%s message=%s",
            request.url.path,
            getattr(request.state, "request_id", "-"),
            exc.code,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": "error",
                "code": exc.code,
                "message": exc.message,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.warning(
            "[ValidationError] path=%s request_id=%s errors=%s",
            request.url.path,
            getattr(request.state, "request_id", "-"),
            exc.errors(),
        )
        return JSONResponse(
            status_code=422,
            content={
                "type": "error",
                "code": "REQUEST_VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        logger.warning(
            "[HTTPException] path=%s request_id=%s status=%s detail=%s",
            request.url.path,
            getattr(request.state, "request_id", "-"),
            exc.status_code,
            exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": "error",
                "code": "HTTP_ERROR",
                "message": exc.detail if isinstance(exc.detail, str) else "HTTP 请求错误",
                "details": exc.detail if not isinstance(exc.detail, str) else None,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "[UnhandledException] path=%s request_id=%s",
            request.url.path,
            getattr(request.state, "request_id", "-"),
        )
        return JSONResponse(
            status_code=500,
            content={
                "type": "error",
                "code": "INTERNAL_SERVER_ERROR",
                "message": "服务内部异常，请稍后重试",
            },
        )
