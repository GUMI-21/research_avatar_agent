"""HTTP and mock adapters for the supported LLM providers."""

import json
from abc import ABC
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

import httpx

from app.adapters.llm.base import (
    LLMClient,
    LLMClientConfig,
    LLMRequest,
    LLMResult,
    LLMStreamChunk,
    LLMToolCall,
    LLMUsage,
)
from app.adapters.llm.errors import (
    LLMConfigurationError,
    LLMProviderError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.schemas.llm import LLMProvider


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


# openAi 工具协议
def _openai_tools(request: LLMRequest) -> list[dict[str, object]]:
    return [
        {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": dict(tool.input_schema),
            "strict": True,
        }
        for tool in request.tools
    ]


# 继承LLMclient抽象基
class MockLLMAdapter(LLMClient):
    """Deterministic local adapter used before configuration and in tests."""

    async def generate(self, request: LLMRequest) -> LLMResult:
        return LLMResult(
            text=f"Echo: {request.message}",
            provider=LLMProvider.MOCK,
            model="mock-echo",
        )


# 中间类
class _HTTPAdapter(LLMClient, ABC):
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

    # 通用 HTTP/SSE 工作
    async def _stream_json(
        self,
        path: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> AsyncIterator[dict[str, Any]]:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds,
                transport=self._transport,
                follow_redirects=False,
            ) as client:
                async with client.stream(
                    "POST", url, headers=headers, json=payload
                ) as response:
                    response.raise_for_status()
                    # process data
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        raw_data = line.removeprefix("data:").strip()
                        if raw_data == "[DONE]":
                            return
                        try:
                            data = json.loads(raw_data)
                        except ValueError as error:
                            raise LLMResponseError(self.config.provider) from error
                        if not isinstance(data, dict):
                            raise LLMResponseError(self.config.provider)
                        yield data
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
                **(
                    {"instructions": request.instructions}
                    if request.instructions
                    else {}
                ),
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

    # token流式输出
    async def stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        emitted = False
        reported_usage: LLMUsage | None = None
        async for event in self._stream_json(
            "responses",
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
            },
            payload={
                "model": self.config.model,
                "input": request.message,
                "max_output_tokens": self.config.max_output_tokens,
                "stream": True,
                **(
                    {
                        "tools": _openai_tools(request),
                        "tool_choice": "auto",
                        "parallel_tool_calls": False,
                    }
                    if request.tools
                    else {}
                ),
                **(
                    {"instructions": request.instructions}
                    if request.instructions
                    else {}
                ),
            },
        ):
            event_type = event.get("type")
            if event_type in {"response.failed", "error"}:
                raise LLMProviderError(
                    self.config.provider, "OpenAI response stream failed"
                )
            # 一次新增的文本
            delta = event.get("delta")
            if event_type == "response.output_text.delta" and isinstance(delta, str):
                emitted = emitted or bool(delta)
                if delta:
                    yield LLMStreamChunk(
                        text=delta,
                        provider=self.config.provider,
                        model=self.config.model,
                    )
            if event_type == "response.output_item.done":
                item = event.get("item")
                if isinstance(item, dict) and item.get("type") == "function_call":
                    name = item.get("name")
                    raw_arguments = item.get("arguments")
                    if not isinstance(name, str) or not isinstance(raw_arguments, str):
                        raise LLMResponseError(self.config.provider)
                    try:
                        arguments = json.loads(raw_arguments)
                    except ValueError as error:
                        raise LLMResponseError(self.config.provider) from error
                    if not isinstance(arguments, dict):
                        raise LLMResponseError(self.config.provider)
                    emitted = True
                    yield LLMStreamChunk(
                        text="",
                        provider=self.config.provider,
                        model=self.config.model,
                        tool_call=LLMToolCall(name=name, arguments=arguments),
                    )
            # 获取本次消耗的token
            if event_type == "response.completed":
                response = event.get("response")
                usage = response.get("usage") if isinstance(response, dict) else None
                if isinstance(usage, dict):
                    details = usage.get("input_tokens_details")
                    details = details if isinstance(details, dict) else {}
                    reported_usage = LLMUsage(
                        input_tokens=_optional_int(usage.get("input_tokens")),
                        output_tokens=_optional_int(usage.get("output_tokens")),
                        cache_read_tokens=_optional_int(
                            details.get("cached_tokens")
                        ),
                        cache_write_tokens=_optional_int(
                            details.get("cache_write_tokens")
                        ),
                    )
        if not emitted:
            raise LLMResponseError(self.config.provider)
        if reported_usage is not None:
            yield LLMStreamChunk(
                text="",
                provider=self.config.provider,
                model=self.config.model,
                usage=reported_usage,
            )

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
                "messages": (
                    [{"role": "system", "content": request.instructions}]
                    if request.instructions
                    else []
                ) + [{"role": "user", "content": request.message}],
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

    # 流式输出
    async def stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        emitted = False
        reported_usage: LLMUsage | None = None
        async for event in self._stream_json(
            "chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
            },
            payload={
                "model": self.config.model,
                "messages": (
                    [{"role": "system", "content": request.instructions}]
                    if request.instructions
                    else []
                ) + [{"role": "user", "content": request.message}],
                "max_tokens": self.config.max_output_tokens,
                "stream": True,
                "stream_options": {"include_usage": True},
            },
        ):
            if "error" in event:
                raise LLMProviderError(
                    self.config.provider, "DeepSeek response stream failed"
                )
            usage = event.get("usage")
            if isinstance(usage, dict):
                reported_usage = LLMUsage(
                    input_tokens=_optional_int(usage.get("prompt_tokens")),
                    output_tokens=_optional_int(usage.get("completion_tokens")),
                    cache_read_tokens=_optional_int(
                        usage.get("prompt_cache_hit_tokens")
                    ),
                )
            choices = event.get("choices")
            if not isinstance(choices, list) or not choices:
                continue
            choice = choices[0]
            if not isinstance(choice, dict):
                continue
            delta = choice.get("delta")
            if not isinstance(delta, dict):
                continue
            text = delta.get("content")
            if isinstance(text, str) and text:
                emitted = True
                yield LLMStreamChunk(
                    text=text,
                    provider=self.config.provider,
                    model=self.config.model,
                )
        if not emitted:
            raise LLMResponseError(self.config.provider)
        if reported_usage is not None:
            yield LLMStreamChunk(
                text="",
                provider=self.config.provider,
                model=self.config.model,
                usage=reported_usage,
            )


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
                **(
                    {"systemInstruction": {"parts": [{"text": request.instructions}]}}
                    if request.instructions
                    else {}
                ),
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

    # 流式输出
    async def stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        model = quote(self.config.model, safe="-._")
        emitted = False
        reported_usage: LLMUsage | None = None
        async for event in self._stream_json(
            f"models/{model}:streamGenerateContent?alt=sse",
            headers={
                "x-goog-api-key": self._api_key(),
                "Content-Type": "application/json",
            },
            payload={
                "contents": [
                    {"role": "user", "parts": [{"text": request.message}]}
                ],
                **(
                    {"systemInstruction": {"parts": [{"text": request.instructions}]}}
                    if request.instructions
                    else {}
                ),
                "generationConfig": {
                    "maxOutputTokens": self.config.max_output_tokens
                },
            },
        ):
            if "error" in event:
                raise LLMProviderError(
                    self.config.provider, "Gemini response stream failed"
                )
            usage = event.get("usageMetadata")
            if isinstance(usage, dict):
                candidate_tokens = _optional_int(usage.get("candidatesTokenCount"))
                thought_tokens = _optional_int(usage.get("thoughtsTokenCount"))
                reported_usage = LLMUsage(
                    input_tokens=_optional_int(usage.get("promptTokenCount")),
                    output_tokens=(candidate_tokens or 0) + (thought_tokens or 0),
                    cache_read_tokens=_optional_int(
                        usage.get("cachedContentTokenCount")
                    ),
                )
            candidates = event.get("candidates")
            if not isinstance(candidates, list) or not candidates:
                continue
            candidate = candidates[0]
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            parts = content.get("parts")
            if not isinstance(parts, list):
                continue
            for part in parts:
                if not isinstance(part, dict) or part.get("thought") is True:
                    continue
                text = part.get("text")
                if isinstance(text, str) and text:
                    emitted = True
                    yield LLMStreamChunk(
                        text=text,
                        provider=self.config.provider,
                        model=self.config.model,
                    )
        if not emitted:
            raise LLMResponseError(self.config.provider)
        if reported_usage is not None:
            yield LLMStreamChunk(
                text="",
                provider=self.config.provider,
                model=self.config.model,
                usage=reported_usage,
            )
