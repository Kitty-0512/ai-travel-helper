"""Shared provider response model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ProviderResult:
    """Normalized provider output before converting back to tool dicts."""

    success: bool
    data: dict[str, Any]
    source: str
    is_fallback: bool = False
    error_code: str = ""
    message: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.data)
        payload["source"] = self.source
        payload["is_fallback"] = self.is_fallback
        if self.warnings:
            payload["warnings"] = list(self.warnings)
        if not self.success and self.message:
            payload["error"] = self.message
        if self.error_code:
            payload["error_code"] = self.error_code
        return payload
