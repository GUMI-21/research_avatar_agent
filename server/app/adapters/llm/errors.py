"""Errors shared by LLM adapters and the HTTP layer."""

from app.schemas.llm import LLMProvider


class LLMError(Exception):
    """Base error for expected LLM failures."""


class LLMConfigurationError(LLMError):
    """Raised when runtime provider settings are incomplete."""


class LLMTimeoutError(LLMError):
    """Raised when a provider does not answer before the configured timeout."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider
        super().__init__(f"{provider.value} request timed out")


class LLMProviderError(LLMError):
    """Raised for provider HTTP or connection failures."""

    def __init__(
        self,
        provider: LLMProvider,
        message: str,
        status_code: int | None = None,
    ) -> None:
        self.provider = provider
        self.status_code = status_code
        super().__init__(message)


class LLMResponseError(LLMError):
    """Raised when a successful provider response contains no usable text."""

    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider
        super().__init__(f"{provider.value} returned an invalid response")
