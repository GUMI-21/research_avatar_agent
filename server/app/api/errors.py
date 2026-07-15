"""Translate internal LLM failures into stable HTTP errors."""

from fastapi import HTTPException, status

from app.adapters.llm.errors import (
    LLMConfigurationError,
    LLMError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
)


def llm_http_exception(error: LLMError) -> HTTPException:
    """Map provider-independent failures to client-facing HTTP status codes."""
    if isinstance(error, LLMConfigurationError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )
    if isinstance(error, LLMTimeoutError):
        return HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="LLM provider request timed out",
        )
    if isinstance(error, (LLMProviderError, LLMResponseError)):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM provider request failed",
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected LLM error",
    )
