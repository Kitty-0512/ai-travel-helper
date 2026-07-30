"""Text embedding helpers for memory vectors."""

from __future__ import annotations

import hashlib
import math
import struct

import httpx

from app.core.config import settings


async def embed_text(text: str) -> list[float]:
    """Return a fixed-dim embedding. Uses remote API when configured, else local hash."""
    cleaned = (text or "").strip()
    if not cleaned:
        return [0.0] * settings.embedding_dim

    if settings.embedding_base_url and settings.embedding_api_key:
        try:
            return await _remote_embed(cleaned)
        except Exception:
            pass
    return _local_hash_embed(cleaned, settings.embedding_dim)


async def _remote_embed(text: str) -> list[float]:
    url = settings.embedding_base_url.rstrip("/") + "/embeddings"
    headers = {
        "Authorization": f"Bearer {settings.embedding_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"model": settings.embedding_model, "input": text}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        vector = data["data"][0]["embedding"]
        return _fit_dim(vector, settings.embedding_dim)


def _local_hash_embed(text: str, dim: int) -> list[float]:
    """Deterministic feature-hashing embedding (no external model required)."""
    vec = [0.0] * dim
    tokens = text.lower().replace("，", " ").replace(",", " ").split()
    if not tokens:
        tokens = [text]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        # Use successive 4-byte chunks as feature indices / signs
        for i in range(0, min(len(digest), 32), 4):
            chunk = digest[i : i + 4]
            if len(chunk) < 4:
                break
            idx = struct.unpack(">I", chunk)[0] % dim
            sign = 1.0 if (chunk[0] & 1) == 0 else -1.0
            vec[idx] += sign
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _fit_dim(vector: list[float], dim: int) -> list[float]:
    if len(vector) == dim:
        return vector
    if len(vector) > dim:
        return vector[:dim]
    return vector + [0.0] * (dim - len(vector))
