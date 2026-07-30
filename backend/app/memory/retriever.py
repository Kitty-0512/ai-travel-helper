"""Retrieve user preference memory for prompt injection."""

from __future__ import annotations

import logging

from app.core.config import settings
from app.memory.embeddings import embed_text
from app.memory.models import MemoryRecord, UserProfile
from app.memory.storage import MemoryStorage

logger = logging.getLogger(__name__)


async def retrieve_profile(
    storage: MemoryStorage,
    user_id: str,
    query: str = "",
) -> UserProfile:
    """Redis first; on miss, rebuild from Postgres (vector + recent)."""
    if not user_id or not storage.ready:
        return UserProfile()

    cached = await storage.get_profile(user_id)
    if cached is not None and not _profile_empty(cached):
        # refresh TTL
        await storage.set_profile(user_id, cached)
        return cached

    profile = UserProfile()
    records: list[MemoryRecord] = []
    try:
        if query:
            emb = await embed_text(query)
            records = await storage.search_similar(user_id, emb, top_k=settings.memory_top_k)
        if not records:
            records = await storage.list_memories(user_id, limit=settings.memory_top_k)
    except Exception as e:
        logger.warning("[Memory] retrieve failed: %s", e)
        return UserProfile()

    for rec in records:
        _apply_record(profile, rec)

    if not _profile_empty(profile):
        await storage.set_profile(user_id, profile)
    return profile


def profile_to_prompt(profile: UserProfile) -> str:
    return profile.to_prompt_text()


def _profile_empty(profile: UserProfile) -> bool:
    return not any(
        [
            profile.style,
            profile.interests,
            profile.dislike,
            profile.budget,
            profile.transport,
            profile.constraints,
        ]
    )


def _apply_record(profile: UserProfile, rec: MemoryRecord) -> None:
    structured = rec.structured or {}
    mtype = rec.memory_type

    if mtype == "style" and structured.get("style"):
        profile.style = str(structured["style"])
    elif mtype == "interest":
        vals = structured.get("interests") or structured.get("interest") or []
        if isinstance(vals, str):
            vals = [vals]
        profile.interests = list(dict.fromkeys([*profile.interests, *[str(v) for v in vals]]))
    elif mtype == "dislike":
        vals = structured.get("dislike") or []
        if isinstance(vals, str):
            vals = [vals]
        profile.dislike = list(dict.fromkeys([*profile.dislike, *[str(v) for v in vals]]))
    elif mtype == "budget" and structured.get("budget"):
        profile.budget = str(structured["budget"])
    elif mtype == "transport" and structured.get("transport"):
        profile.transport = str(structured["transport"])
    elif mtype in ("constraint", "note"):
        vals = structured.get("constraints") or [rec.content]
        if isinstance(vals, str):
            vals = [vals]
        profile.constraints = list(dict.fromkeys([*profile.constraints, *[str(v) for v in vals]]))

    # Also fold free-form structured fields from extractor dumps
    if structured.get("style") and not profile.style:
        profile.style = str(structured["style"])
    for key, attr in (("interests", "interests"), ("dislike", "dislike"), ("constraints", "constraints")):
        extra = structured.get(key)
        if isinstance(extra, list) and extra:
            current = getattr(profile, attr)
            setattr(profile, attr, list(dict.fromkeys([*current, *[str(v) for v in extra]])))
