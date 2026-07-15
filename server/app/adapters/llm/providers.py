"""HTTP and mock adapters for the supported LLM providers."""

from typing import Any
from urllib.parse import quote

import httpx

from app.adapters.llm.base import (
    LLMClient,
    LLMClientConfig,
    LLMRequest,
    LLMResult,
)
from app.adapters.llm.errors import (
    LLMConfigurationError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.schemas.llm import LLMProvider


class MockLLMAdapter(LLMClient):
    """Deterministic local adapter used before configuration and in tests."""

    async def generate(self, request: LLMRequest) -> LLMResult:
        return LLMResult(
            text=f"Echo: {request.message}",
            provider=LLMProvider.MOCK,
            model="mock-echo",
        )


class _HTTPAdapter(LLMClient):
    """Shared HTTP error handling for provider-specific request formats."""

    def __init__(
        self,
        config: LLMClientConfig,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if config.api_key is None:
            raise LLMConfigurationError(
                f"API key is required for provider '{config.provider.value}'"
            )
        self.config = config
        self._transport = transport

    async def _post_json(
        self,
        path: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.TimeoutException as error:
            raise LLMTimeoutError(self.config.provider) from error
        except httpx.HTTPStatusError as error:
            raise LLMProviderError(
                self.config.provider,
                f"{self.config.provider.value} returned HTTP "
                f"{error.response.status_code}",
                status_code=error.response.status_code,
            ) from error
        except httpx.RequestError as error:
            raise LLMProviderError(
                self.config.provider,
                f"Could not connect to {self.config.provider.value}",
            ) from error

        try:
            data = response.json()
        except ValueError as error:
            raise LLMResponseError(self.config.provider) from error
        if not isinstance(data, dict):
            raise LLMResponseError(self.config.provider)
        return data

    def _api_key(self) -> str:
        api_key = self.config.api_key
        if api_key is None:
            raise LLMConfigurationError("API key is not configured")
        return api_key.get_secret_value()


class OpenAIAdapter(_HTTPAdapter):
    """OpenAI Responses API adapter."""

    async def generate(self, request: LLMRequest) -> LLMResult:
        data = await self._post_json(
            "responses",
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
            },
            payload={
                "model": self.config.model,
                "input": request.message,
                "max_output_tokens": self.config.max_output_tokens,
            },
        )

        text_parts: list[str] = []
        for output_item in data.get("output", []):
            if not isinstance(output_item, dict):
                continue
            for content_item in output_item.get("content", []):
                if not isinstance(content_item, dict):
                    continue
                text = content_item.get("text")
                if content_item.get("type") == "output_text" and isinstance(text, str):
                    text_parts.append(text)
        text = "".join(text_parts).strip()
        if not text:
            raise LLMResponseError(self.config.provider)
        return LLMResult(text=text, provider=self.config.provider, model=self.config.model)

class DeepSeekAdapter(_HTTPAdapter):
    """DeepSeek OpenAI-compatible Chat Completions adapter."""

    async def generate(self, request: LLMRequest) -> LLMResult:
        data = await self._post_json(
            "chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
            },
            payload={
                "model": self.config.model,
                "messages": [{"role": "user", "content": request.message}],
                "max_tokens": self.config.max_output_tokens,
            },
        )
        try:
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as error:
            raise LLMResponseError(self.config.provider) from error
        if not text:
            raise LLMResponseError(self.config.provider)
        return LLMResult(text=text, provider=self.config.provider, model=self.config.model)


class GeminiAdapter(_HTTPAdapter):
    """Google Gemini generateContent REST adapter."""

    async def generate(self, request: LLMRequest) -> LLMResult:
        model = quote(self.config.model, safe="-._")
        data = await self._post_json(
            f"models/{model}:generateContent",
            headers={
                "x-goog-api-key": self._api_key(),
                "Content-Type": "application/json",
            },
            payload={
                "contents": [
                    {"role": "user", "parts": [{"text": request.message}]}
                ],
                "generationConfig": {
                    "maxOutputTokens": self.config.max_output_tokens
                },
            },
        )
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(
                part["text"]
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ).strip()
        except (KeyError, IndexError, TypeError) as error:
            raise LLMResponseError(self.config.provider) from error
        if not text:
            raise LLMResponseError(self.config.provider)
        return LLMResult(text=text, provider=self.config.provider, model=self.config.model)
