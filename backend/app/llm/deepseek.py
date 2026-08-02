"""DeepSeek API 封装 —— httpx 直发，流式 SSE 解析"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import AsyncGenerator

import httpx

from app.core.config import settings
from app.core.exceptions import LLMAPIError, LLMTimeoutError

logger = logging.getLogger(__name__)

# DSML 标签模式：DeepSeek 偶尔在 content 中输出 tool_calls 文本而非使用标准 tool_calls delta
_DSML_TAG_RE = re.compile(
    r'</?(?:tool_calls|function_calls|invoke|parameter)\b[^>]*>',
    re.IGNORECASE,
)
# 检测 content 中是否包含 DSML（用于日志和调试）
_DSML_DETECT_RE = re.compile(
    r'<(?:tool_calls|function_calls|invoke)\b',
    re.IGNORECASE,
)


def _strip_dsml(text: str) -> str:
    """从流式文本中移除 DSML 标签，返回干净文本。"""
    return _DSML_TAG_RE.sub('', text)


def _has_dsml(text: str) -> bool:
    """检测文本中是否包含 DSML 工具调用标签。"""
    return bool(_DSML_DETECT_RE.search(text))


@dataclass
class LLMResponse:
    """聚合一次 LLM 调用的完整结果"""
    content: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = ""


def _trim_messages(messages: list[dict]) -> list[dict]:
    budget = settings.deepseek_message_char_budget
    total = 0
    kept: list[dict] = []
    for msg in reversed(messages):
        content = msg.get("content")
        size = len(content) if isinstance(content, str) else len(json.dumps(content, ensure_ascii=False, default=str))
        if kept and total + size > budget:
            break
        kept.append(msg)
        total += size
    kept.reverse()
    return kept or messages[-1:]


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, LLMTimeoutError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {408, 409, 429, 500, 502, 503, 504}
    return isinstance(exc, httpx.HTTPError)


async def chat_completion_stream(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> AsyncGenerator:
    """
    调用 DeepSeek API（流式）的异步生成器。

    实时 yield 文本片段（str），最后 yield 完整 LLMResponse 对象。
    调用方通过 isinstance 区分：
        async for item in chat_completion_stream(...):
            if isinstance(item, str):      # 文本 chunk，实时推送给前端
                ...
            elif isinstance(item, LLMResponse):  # 最终结果，含 tool_calls
                ...

    DeepSeek API 完全兼容 OpenAI 的 chat/completions 格式。
    """
    url = f"{settings.deepseek_base_url}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}",
    }
    payload: dict = {
        "model": model or settings.deepseek_model,
        "messages": _trim_messages(messages),
        "max_tokens": max_tokens or settings.deepseek_max_tokens,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    attempt = 0
    while True:
        try:
            async with httpx.AsyncClient(timeout=settings.deepseek_timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        body = await response.aread()
                        raise LLMAPIError(f"{response.status_code}: {body.decode()}")

                    result = LLMResponse()
                    tool_call_buffer: dict[int, dict] = {}

                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        finish = chunk.get("choices", [{}])[0].get("finish_reason", "")
                        content = delta.get("content", "")
                        if content:
                            result.content += content
                            # 过滤 DSML 工具调用标签，禁止内部协议泄漏到前端
                            clean = _strip_dsml(content)
                            if _has_dsml(content):
                                logger.info(
                                    "[LLM] DSML stripped from chunk: %s",
                                    content[:120].replace('\n', '\\n'),
                                )
                            if clean.strip():
                                yield clean

                        for tc in delta.get("tool_calls", []):
                            idx = tc.get("index", 0)
                            if idx not in tool_call_buffer:
                                tool_call_buffer[idx] = {
                                    "id": tc.get("id", ""),
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            buf = tool_call_buffer[idx]
                            if tc.get("id"):
                                buf["id"] = tc["id"]
                            if tc.get("function", {}).get("name"):
                                buf["function"]["name"] += tc["function"]["name"]
                            if tc.get("function", {}).get("arguments"):
                                buf["function"]["arguments"] += tc["function"]["arguments"]

                        if finish:
                            result.finish_reason = finish

                    result.tool_calls = [tool_call_buffer[k] for k in sorted(tool_call_buffer)]
                    yield result
                    return
        except httpx.TimeoutException as exc:
            if attempt >= settings.deepseek_max_retries:
                raise LLMTimeoutError() from exc
            logger.warning("[LLM] stream timeout, retry=%s", attempt + 1)
        except Exception as exc:
            if attempt >= settings.deepseek_max_retries or not _should_retry(exc):
                if isinstance(exc, (LLMAPIError, LLMTimeoutError)):
                    raise
                raise LLMAPIError(str(exc)) from exc
            logger.warning("[LLM] stream retry=%s error=%s", attempt + 1, exc)
        attempt += 1
        await asyncio.sleep(settings.deepseek_retry_backoff_seconds * (2**attempt))


async def chat_completion_simple(
    messages: list[dict],
    model: str | None = None,
    max_tokens: int | None = None,
) -> str:
    """非流式调用，返回纯文本（用于最终 JSON 提取等简单场景）"""
    url = f"{settings.deepseek_base_url}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.deepseek_api_key}",
    }
    payload = {
        "model": model or settings.deepseek_model,
        "messages": _trim_messages(messages),
        "max_tokens": max_tokens or 2000,
        "stream": False,
    }

    attempt = 0
    while True:
        try:
            async with httpx.AsyncClient(timeout=settings.deepseek_timeout) as client:
                resp = await client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    raise LLMAPIError(f"{resp.status_code}: {resp.text}")
                data = resp.json()
                return data["choices"][0]["message"]["content"]
        except httpx.TimeoutException as exc:
            if attempt >= settings.deepseek_max_retries:
                raise LLMTimeoutError() from exc
            logger.warning("[LLM] simple timeout, retry=%s", attempt + 1)
        except Exception as exc:
            if attempt >= settings.deepseek_max_retries or not _should_retry(exc):
                if isinstance(exc, (LLMAPIError, LLMTimeoutError)):
                    raise
                raise LLMAPIError(str(exc)) from exc
            logger.warning("[LLM] simple retry=%s error=%s", attempt + 1, exc)
        attempt += 1
        await asyncio.sleep(settings.deepseek_retry_backoff_seconds * (2**attempt))
