"""Memory manager facade used by agent loop and HTTP routes."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.memory.embeddings import embed_text
from app.memory.extractor import extract_preferences
from app.memory.models import ExtractedPreferences, MemoryRecord, UserProfile
from app.memory.retriever import profile_to_prompt, retrieve_profile
from app.memory.storage import storage

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self) -> None:
        self.storage = storage

    async def startup(self) -> None:
        await self.storage.connect()

    async def shutdown(self) -> None:
        await self.storage.close()

    @property
    def available(self) -> bool:
        return settings.memory_enabled and self.storage.ready

    async def retrieve_for_prompt(self, user_id: str | None, query: str = "") -> str:
        """Return prompt injection text; empty string on miss/failure."""
        if not user_id or not self.available:
            return ""
        try:
            profile = await retrieve_profile(self.storage, user_id, query=query)
            return profile_to_prompt(profile)
        except Exception as e:
            logger.warning("[Memory] retrieve_for_prompt failed: %s", e)
            return ""

    async def extract_and_save(
        self,
        user_id: str | None,
        user_text: str,
        source_session_id: str | None = None,
        styles: list[str] | None = None,
    ) -> ExtractedPreferences:
        if not user_id or not self.available:
            return ExtractedPreferences()

        try:
            pref = await extract_preferences(user_text) if user_text.strip() else ExtractedPreferences()
            if styles:
                for s in styles:
                    if s and s not in pref.interests:
                        pref.interests.append(s)

            if pref.is_empty():
                return pref

            await self._persist_extracted(user_id, pref, source_session_id)
            return pref
        except Exception as e:
            logger.warning("[Memory] extract_and_save failed: %s", e)
            return ExtractedPreferences()

    async def list_memories(self, user_id: str) -> list[MemoryRecord]:
        if not user_id or not self.available:
            return []
        return await self.storage.list_memories(user_id)

    async def delete_memories(self, user_id: str) -> int:
        if not user_id or not self.available:
            return 0
        count = await self.storage.soft_delete_all(user_id)
        await self.storage.delete_profile(user_id)
        return count

    async def delete_memory(self, user_id: str, memory_id: str | UUID) -> bool:
        if not user_id or not self.available:
            return False
        ok = await self.storage.soft_delete_one(user_id, memory_id)
        # Invalidate short-term cache so next retrieve rebuilds from PG
        await self.storage.delete_profile(user_id)
        return ok

    async def get_profile(self, user_id: str) -> UserProfile:
        if not user_id or not self.available:
            return UserProfile()
        return await retrieve_profile(self.storage, user_id)

    async def _persist_extracted(
        self,
        user_id: str,
        pref: ExtractedPreferences,
        source_session_id: str | None,
    ) -> None:
        # Update Redis aggregate first
        profile = await self.storage.get_profile(user_id) or UserProfile()
        profile.merge_extracted(pref)
        await self.storage.set_profile(user_id, profile)

        rows: list[tuple[str, str, dict[str, Any]]] = []
        if pref.style:
            rows.append(("style", f"旅行风格：{pref.style}", {"style": pref.style}))
        if pref.interests:
            rows.append(
                (
                    "interest",
                    f"兴趣：{'、'.join(pref.interests)}",
                    {"interests": pref.interests},
                )
            )
        if pref.dislike:
            rows.append(
                (
                    "dislike",
                    f"避免：{'、'.join(pref.dislike)}",
                    {"dislike": pref.dislike},
                )
            )
        if pref.budget:
            rows.append(("budget", f"预算：{pref.budget}", {"budget": pref.budget}))
        if pref.transport:
            rows.append(
                ("transport", f"出行方式：{pref.transport}", {"transport": pref.transport})
            )
        if pref.constraints:
            rows.append(
                (
                    "constraint",
                    f"约束：{'、'.join(pref.constraints)}",
                    {"constraints": pref.constraints},
                )
            )

        for memory_type, content, structured in rows:
            emb = await embed_text(content)
            await self.storage.insert_memory(
                user_id=user_id,
                memory_type=memory_type,
                content=content,
                structured=structured,
                embedding=emb,
                source_session_id=source_session_id,
            )


memory_manager = MemoryManager()
