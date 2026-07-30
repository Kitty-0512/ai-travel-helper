"""Base helpers shared by provider implementations."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.providers.exceptions import ProviderError
from app.providers.models import ProviderResult


class BaseProvider:
    """Provide common success/error/fallback helpers."""

    upstream_source = "amap"

    def success(self, data: dict[str, Any]) -> dict[str, Any]:
        return ProviderResult(
            success=True,
            data=data,
            source=self.upstream_source,
        ).to_dict()

    def fallback_success(
        self,
        data: dict[str, Any],
        *,
        message: str,
        error_code: str,
    ) -> dict[str, Any]:
        return ProviderResult(
            success=True,
            data=data,
            source="fallback",
            is_fallback=True,
            error_code=error_code,
            warnings=[message],
            message=message,
        ).to_dict()

    def error(self, exc: ProviderError) -> dict[str, Any]:
        return ProviderResult(
            success=False,
            data={},
            source=self.upstream_source,
            error_code=exc.code,
            message=exc.message,
        ).to_dict()

    @property
    def fallback_enabled(self) -> bool:
        return settings.provider_enable_fallback
