"""Smoke test for Planner-Executor SSE flow."""

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter

import httpx

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "kitty-travel"
USER_ID = "trace-e2e-user"


def parse_sse_events(raw: str) -> list[dict]:
    events: list[dict] = []
    normalized = raw.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")

    for block in normalized.split("\n\n"):
        block = block.strip()
        if not block:
            continue

        current: dict = {}
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                current["event"] = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            elif line.startswith("id:"):
                current["id"] = line[3:].strip()

        if not data_lines:
            continue

        payload = "\n".join(data_lines)
        try:
            current["data"] = json.loads(payload)
        except json.JSONDecodeError:
            current["data"] = payload
        events.append(current)

    return events


async def test_generate() -> tuple[bool, str, str | None, str | None]:
    payload = {"destination": "杭州", "days": 2, "styles": []}
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-API-Key": API_KEY,
        "X-User-Id": USER_ID,
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/agent/generate",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                return False, f"HTTP {response.status_code}: {body.decode()}", None, None

            chunks: list[str] = []
            async for chunk in response.aiter_text():
                chunks.append(chunk)

    events = parse_sse_events("".join(chunks))
    types = Counter(ev.get("event") for ev in events)

    required = {"agent_think", "tool_call", "tool_result", "chunk", "itinerary_json", "done"}
    missing = required - set(types)
    if missing:
        return False, f"missing events: {sorted(missing)}; got {dict(types)}", None, None

    done_ev = next(ev for ev in events if ev.get("event") == "done")
    done_data = done_ev.get("data", {})
    if not isinstance(done_data, dict):
        return False, "done payload is not an object", None, None

    session_id = done_data.get("session_id")
    if not session_id:
        return False, "done payload missing session_id", None, None
    request_id = done_data.get("request_id")
    if not request_id:
        return False, "done payload missing request_id", None, None

    for key in ("destination", "days", "places_count", "places_detail"):
        if key not in done_data:
            return False, f"done payload missing {key}", None, None

    itinerary_ev = next(ev for ev in events if ev.get("event") == "itinerary_json")
    itinerary_data = itinerary_ev.get("data", {})
    if not isinstance(itinerary_data, dict):
        return False, "itinerary_json payload is not an object", None, None
    if "days" not in itinerary_data or "allPlaces" not in itinerary_data:
        return False, "itinerary_json missing days/allPlaces", None, None

    tool_calls = [ev.get("data", {}) for ev in events if ev.get("event") == "tool_call"]
    tool_names = {tc.get("tool") for tc in tool_calls if isinstance(tc, dict)}
    mcp_tools = {"search_place", "get_weather", "calculate_route"}
    if not tool_names & mcp_tools:
        return False, f"expected MCP tool calls, got {tool_names}", None, None

    for item in tool_calls:
        if not isinstance(item, dict):
            continue
        if item.get("status") != "running" or not item.get("message"):
            return False, f"tool_call missing status/message: {item}", None, None

    tool_results = [ev.get("data", {}) for ev in events if ev.get("event") == "tool_result"]
    if not tool_results:
        return False, "missing tool_result events", None, None

    provider_sources = {
        item.get("result_preview", {}).get("source")
        for item in tool_results
        if isinstance(item, dict) and isinstance(item.get("result_preview"), dict)
    }
    if "amap" not in provider_sources and "fallback" not in provider_sources:
        return False, f"tool_result missing provider metadata: {provider_sources}", None, None

    for item in tool_results:
        if not isinstance(item, dict):
            continue
        if item.get("status") not in {"success", "error"}:
            return False, f"tool_result missing status: {item}", None, None
        if "duration" not in item:
            return False, f"tool_result missing duration: {item}", None, None

    return True, (
        f"generate ok: events={dict(types)}, tools={sorted(tool_names)}, "
        f"session_id={session_id}, request_id={request_id}"
    ), session_id, request_id


async def test_chat(session_id: str) -> tuple[bool, str]:
    payload = {"session_id": session_id, "message": "第二天少安排一个景点"}
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-API-Key": API_KEY,
        "X-User-Id": USER_ID,
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        async with client.stream(
            "POST",
            f"{BASE_URL}/api/agent/chat",
            headers=headers,
            json=payload,
        ) as response:
            if response.status_code != 200:
                body = await response.aread()
                return False, f"chat HTTP {response.status_code}: {body.decode()}"

            chunks: list[str] = []
            async for chunk in response.aiter_text():
                chunks.append(chunk)

    events = parse_sse_events("".join(chunks))
    types = Counter(ev.get("event") for ev in events)
    if "done" not in types:
        return False, f"chat missing done event; got {dict(types)}"

    done_data = next(ev["data"] for ev in events if ev.get("event") == "done")
    if not isinstance(done_data, dict) or not done_data.get("session_id"):
        return False, "chat done payload missing session_id"

    return True, f"chat ok: events={dict(types)}"


async def main() -> int:
    ok, msg, session_id, _request_id = await test_generate()
    print(msg)
    if not ok:
        return 1

    ok, msg = await test_chat(session_id)
    print(msg)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
