"""Session persistence backed by PostgreSQL (with JSON-file fallback for dev)."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

# JSON-file path for local dev persistence (survives restarts)
_FALLBACK_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "sessions.json"


class SessionRepository:
    """Persist trip planning sessions to PostgreSQL.

    Follows the same pattern as MemoryStorage / TraceStorage:
    - asyncpg pool + JSON-file fallback
    - connect() / close() / ready lifecycle
    - safe defaults when not ready
    """

    def __init__(self) -> None:
        self._pool: asyncpg.Pool | None = None
        self._ready = False
        self._backend: str = "none"
        # JSON-file fallback for local dev without PG
        self._fallback: dict[str, dict[str, Any]] = {}
        self._by_user: dict[str, list[str]] = {}

    # ── lifecycle ────────────────────────────────────────────

    async def connect(self) -> None:
        try:
            self._pool = await asyncpg.create_pool(
                settings.database_url, min_size=1, max_size=3
            )
            async with self._pool.acquire() as conn:
                await conn.execute("SELECT 1")
            self._ready = True
            self._backend = "postgres"
            logger.info("[SessionRepo] connected to PostgreSQL")
        except Exception:
            if settings.env == "development":
                self._ready = True
                self._backend = "json_file"
                self._load_from_file()
                logger.warning(
                    "[SessionRepo] PG unavailable, using JSON file: %s (%d sessions loaded)",
                    _FALLBACK_FILE, len(self._fallback),
                )
            else:
                logger.exception("[SessionRepo] failed to connect")

    async def close(self) -> None:
        if self._pool is not None:
            try:
                await self._pool.close()
            except Exception:
                pass
            self._pool = None
        self._fallback.clear()
        self._by_user.clear()
        self._ready = False
        self._backend = "none"

    @property
    def ready(self) -> bool:
        return self._ready

    # ── CRUD ─────────────────────────────────────────────────

    async def upsert(
        self,
        session_id: str,
        user_id: str,
        destination: str,
        days: int,
        styles: list[str],
        itinerary: dict | None,
        messages: list[dict],
        places_detail: list[dict] | None = None,
    ) -> None:
        """Create or update a session record."""
        if not self._ready:
            return
        if self._backend == "json_file":
            record = {
                "session_id": session_id,
                "user_id": user_id,
                "destination": destination,
                "days": days,
                "styles": json.dumps(styles, ensure_ascii=False),
                "itinerary": json.dumps(itinerary) if itinerary else None,
                "messages": json.dumps(messages, ensure_ascii=False),
                "places_detail": (
                    json.dumps(places_detail, ensure_ascii=False)
                    if places_detail
                    else None
                ),
                "created_at": self._fallback.get(session_id, {}).get("created_at") or _now_iso(),
                "updated_at": _now_iso(),
            }
            self._fallback[session_id] = record
            if user_id not in self._by_user:
                self._by_user[user_id] = []
            if session_id not in self._by_user[user_id]:
                self._by_user[user_id].append(session_id)
            self._save_to_file()
            return
        try:
            async with self._pool.acquire() as conn:  # type: ignore[union-attr]
                await conn.execute(
                    """
                    INSERT INTO travel_sessions
                        (session_id, user_id, destination, days, styles,
                         itinerary, messages, places_detail)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb)
                    ON CONFLICT (session_id) DO UPDATE SET
                        destination = EXCLUDED.destination,
                        days = EXCLUDED.days,
                        styles = EXCLUDED.styles,
                        itinerary = EXCLUDED.itinerary,
                        messages = EXCLUDED.messages,
                        places_detail = EXCLUDED.places_detail,
                        updated_at = NOW(),
                        is_active = TRUE
                    """,
                    session_id,
                    user_id,
                    destination,
                    days,
                    json.dumps(styles, ensure_ascii=False),
                    json.dumps(itinerary, ensure_ascii=False) if itinerary else None,
                    json.dumps(messages, ensure_ascii=False),
                    (
                        json.dumps(places_detail, ensure_ascii=False)
                        if places_detail
                        else None
                    ),
                )
        except Exception:
            logger.exception("[SessionRepo] upsert failed session=%s", session_id)

    async def list_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return session summaries for one user, newest first."""
        if not self._ready:
            return []
        if self._backend == "json_file":
            ids = self._by_user.get(user_id, [])
            results = []
            for sid in reversed(ids):
                r = self._fallback.get(sid)
                if r:
                    results.append(self._to_summary(r))
            return results
        try:
            async with self._pool.acquire() as conn:  # type: ignore[union-attr]
                rows = await conn.fetch(
                    """
                    SELECT session_id, destination, days, styles, created_at
                    FROM travel_sessions
                    WHERE user_id = $1 AND is_active = TRUE
                    ORDER BY created_at DESC
                    LIMIT 30
                    """,
                    user_id,
                )
                return [self._row_to_summary(r) for r in rows]
        except Exception:
            logger.exception("[SessionRepo] list_by_user failed user=%s", user_id)
            return []

    async def get(self, session_id: str) -> dict[str, Any] | None:
        """Return session detail including itinerary, places, and conversation text."""
        if not self._ready:
            return None
        if self._backend == "json_file":
            rec = self._fallback.get(session_id)
            return self._to_detail(rec) if rec else None
        try:
            async with self._pool.acquire() as conn:  # type: ignore[union-attr]
                row = await conn.fetchrow(
                    """
                    SELECT session_id, destination, days, styles,
                           itinerary, messages, places_detail, created_at
                    FROM travel_sessions
                    WHERE session_id = $1 AND is_active = TRUE
                    """,
                    session_id,
                )
                return self._row_to_detail(row) if row else None
        except Exception:
            logger.exception("[SessionRepo] get failed session=%s", session_id)
            return None

    async def get_full(self, session_id: str) -> dict[str, Any] | None:
        """Return full session data INCLUDING messages (for restoring chat context)."""
        if not self._ready:
            return None
        if self._backend == "json_file":
            rec = self._fallback.get(session_id)
            return dict(rec) if rec else None
        try:
            async with self._pool.acquire() as conn:  # type: ignore[union-attr]
                row = await conn.fetchrow(
                    """
                    SELECT session_id, user_id, destination, days, styles,
                           itinerary, messages, places_detail, created_at
                    FROM travel_sessions
                    WHERE session_id = $1 AND is_active = TRUE
                    """,
                    session_id,
                )
                if row is None:
                    return None
                return {
                    "session_id": row["session_id"],
                    "user_id": row["user_id"],
                    "destination": row["destination"],
                    "days": row["days"],
                    "styles": _parse_json(row.get("styles")),
                    "itinerary": _parse_json(row.get("itinerary")),
                    "messages": _parse_json(row.get("messages")),
                    "places_detail": _parse_json(row.get("places_detail")),
                    "created_at": row["created_at"].isoformat(),
                }
        except Exception:
            logger.exception("[SessionRepo] get_full failed session=%s", session_id)
            return None

    async def delete(self, session_id: str, user_id: str) -> bool:
        """Soft-delete a session. Returns True if a row was affected."""
        if not self._ready:
            return False
        if self._backend == "json_file":
            existed = session_id in self._fallback
            self._fallback.pop(session_id, None)
            lst = self._by_user.get(user_id, [])
            if session_id in lst:
                lst.remove(session_id)
            self._save_to_file()
            return existed
        try:
            async with self._pool.acquire() as conn:  # type: ignore[union-attr]
                result = await conn.execute(
                    "UPDATE travel_sessions SET is_active = FALSE WHERE session_id = $1 AND user_id = $2",
                    session_id,
                    user_id,
                )
                # asyncpg returns a command tag like "UPDATE 1"
                return result == "UPDATE 1"
        except Exception:
            logger.exception(
                "[SessionRepo] delete failed session=%s user=%s", session_id, user_id
            )
            return False

    # ── file persistence ────────────────────────────────────

    def _save_to_file(self) -> None:
        """Write fallback data to JSON file so sessions survive restarts."""
        try:
            _FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "by_user": self._by_user,
                "records": self._fallback,
            }
            with open(_FALLBACK_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, default=str)
        except Exception:
            logger.warning("[SessionRepo] failed to save to %s", _FALLBACK_FILE, exc_info=True)

    def _load_from_file(self) -> None:
        """Load fallback data from JSON file."""
        try:
            if _FALLBACK_FILE.exists():
                with open(_FALLBACK_FILE, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                self._by_user = payload.get("by_user", {})
                self._fallback = payload.get("records", {})
        except Exception:
            logger.warning("[SessionRepo] failed to load from %s", _FALLBACK_FILE, exc_info=True)

    # ── helpers ──────────────────────────────────────────────

    def _row_to_summary(self, row: asyncpg.Record) -> dict[str, Any]:
        return {
            "session_id": row["session_id"],
            "destination": row["destination"],
            "days": row["days"],
            "styles": _parse_json(row.get("styles")),
            "created_at": row["created_at"].isoformat(),
        }

    def _row_to_detail(self, row: asyncpg.Record) -> dict[str, Any]:
        return {
            "session_id": row["session_id"],
            "destination": row["destination"],
            "days": row["days"],
            "styles": _parse_json(row.get("styles")),
            "itinerary": _parse_json(row.get("itinerary")),
            "places_detail": _parse_json(row.get("places_detail")),
            "markdown_text": _extract_markdown(row.get("messages")),
            "created_at": row["created_at"].isoformat(),
        }

    def _to_summary(self, rec: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": rec["session_id"],
            "destination": rec["destination"],
            "days": rec["days"],
            "styles": _parse_json(rec.get("styles")),
            "created_at": _ensure_iso(rec.get("created_at")),
        }

    def _to_detail(self, rec: dict[str, Any]) -> dict[str, Any]:
        return {
            "session_id": rec["session_id"],
            "destination": rec["destination"],
            "days": rec["days"],
            "styles": _parse_json(rec.get("styles")),
            "itinerary": _parse_json(rec.get("itinerary")),
            "places_detail": _parse_json(rec.get("places_detail")),
            "markdown_text": _extract_markdown(rec.get("messages")),
            "created_at": _ensure_iso(rec.get("created_at")),
        }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _ensure_iso(val: Any) -> str:
    if val is None or val == "":
        return ""
    return str(val)


def _parse_json(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val


def _extract_markdown(messages_val: Any) -> str:
    """Extract readable markdown from stored messages (last assistant reply)."""
    messages = _parse_json(messages_val) if isinstance(messages_val, str) else messages_val
    if not isinstance(messages, list):
        return ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    return ""


session_repo = SessionRepository()
