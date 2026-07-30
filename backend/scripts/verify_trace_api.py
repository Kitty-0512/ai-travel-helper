"""Verify trace API can return the recorded request steps."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

BASE_URL = "http://127.0.0.1:8000"
API_KEY = "kitty-travel"
USER_ID = "trace-api-user"


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
        if not data_lines:
            continue
        payload = "\n".join(data_lines)
        try:
            current["data"] = json.loads(payload)
        except json.JSONDecodeError:
            current["data"] = payload
        events.append(current)
    return events


async def main() -> int:
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
            json={"destination": "杭州", "days": 2, "styles": []},
        ) as response:
            if response.status_code != 200:
                print("FAIL generate:", response.status_code, await response.aread())
                return 1
            chunks: list[str] = []
            async for chunk in response.aiter_text():
                chunks.append(chunk)

        events = parse_sse_events("".join(chunks))
        done = next((ev.get("data", {}) for ev in events if ev.get("event") == "done"), {})
        request_id = done.get("request_id")
        if not request_id:
            print("FAIL: done payload missing request_id")
            return 1

        response = await client.get(
            f"{BASE_URL}/api/trace/{request_id}",
            headers={"X-API-Key": API_KEY, "X-User-Id": USER_ID},
        )
        if response.status_code != 200:
            print("FAIL trace api:", response.status_code, response.text)
            return 1

    payload = response.json()
    steps = payload.get("steps", [])
    if not steps:
        print("FAIL: trace steps empty")
        return 1

    actions = {step.get("action") for step in steps}
    required = {"request_start", "planner_complete", "tool_call", "tool_result", "finalize_complete", "request_finish"}
    missing = required - actions
    if missing:
        print("FAIL: missing trace actions", sorted(missing), actions)
        return 1

    if steps != sorted(steps, key=lambda item: item.get("step", 0)):
        print("FAIL: trace steps not sorted")
        return 1

    print("ok trace api:", request_id, "steps=", len(steps), "backend=", payload.get("backend"))
    print("ALL TRACE API TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
