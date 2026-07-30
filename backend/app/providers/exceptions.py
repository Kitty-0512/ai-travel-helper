"""Normalized provider-layer exceptions."""


class ProviderError(Exception):
    """Base class for provider failures."""

    code = "provider_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ProviderTimeoutError(ProviderError):
    code = "timeout"


class ProviderUpstreamError(ProviderError):
    code = "upstream_error"


class ProviderEmptyResultError(ProviderError):
    code = "empty_result"


class ProviderValidationError(ProviderError):
    code = "validation_error"
