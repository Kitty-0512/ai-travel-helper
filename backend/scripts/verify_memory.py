"""Smoke tests for Agent Memory (extract / retrieve / delete / degrade)."""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

# Allow `python scripts/verify_memory.py` from backend/
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "kitty-travel"
USER_ID = f"test-user-{uuid.uuid4().hex[:8]}"


def headers(with_user: bool = True) -> dict:
    h = {"Content-Type": "application/json", "X-API-Key": API_KEY}
    if with_user:
        h["X-User-Id"] = USER_ID
    return h


async def test_missing_user_id() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(f"{BASE_URL}/api/memory", headers=headers(with_user=False))
    assert res.status_code == 400, res.text
    print("ok: GET /memory without X-User-Id -> 400")


async def test_extract_via_manager() -> None:
    """Directly exercise memory_manager if storage is up; otherwise skip write asserts."""
    from app.memory import memory_manager

    await memory_manager.startup()
    if not memory_manager.available:
        print("skip: memory storage unavailable (degraded mode)")
        await memory_manager.shutdown()
        return

    pref = await memory_manager.extract_and_save(
        user_id=USER_ID,
        user_text="我喜欢慢节奏旅行，不喜欢博物馆，喜欢美食和人文。",
        source_session_id="testsess",
    )
    assert not pref.is_empty(), pref
    listed = await memory_manager.list_memories(USER_ID)
    assert len(listed) > 0, listed
    prompt = await memory_manager.retrieve_for_prompt(USER_ID, query="杭州旅行")
    assert "【用户长期偏好】" in prompt, prompt
    assert "museum" in prompt.lower() or "博物馆" in prompt, prompt

    deleted = await memory_manager.delete_memories(USER_ID)
    assert deleted >= 1
    after = await memory_manager.list_memories(USER_ID)
    assert after == []
    prompt2 = await memory_manager.retrieve_for_prompt(USER_ID, query="杭州")
    assert prompt2 == ""
    print("ok: extract / retrieve / delete cycle")
    await memory_manager.shutdown()


async def test_http_memory_api() -> None:
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.get(f"{BASE_URL}/api/memory", headers=headers())
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["user_id"] == USER_ID
        print(
            f"ok: GET /memory available={data.get('available')} "
            f"count={len(data.get('memories', []))}"
        )

        del_res = await client.delete(f"{BASE_URL}/api/memory", headers=headers())
        assert del_res.status_code == 200, del_res.text
        print("ok: DELETE /memory")


async def test_agent_degrades_without_memory() -> None:
    """Generate should still return done even if memory is off / unavailable."""
    payload = {"destination": "杭州", "days": 1, "styles": []}
    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/agent/generate",
            headers={**headers(), "Accept": "text/event-stream"},
            json=payload,
        ) as response:
            assert response.status_code == 200, await response.aread()
            text = ""
            async for chunk in response.aiter_text():
                text += chunk
    # Normalize CRLF quirks from sse-starlette
    normalized = text.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    assert "event: done" in normalized or "event:error" not in normalized[:50]
    assert "event: done" in normalized, "generate did not finish with done"
    print("ok: generate completes with X-User-Id (memory fail-open)")


async def main() -> int:
    await test_missing_user_id()
    await test_extract_via_manager()
    await test_http_memory_api()
    await test_agent_degrades_without_memory()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
