"""Tests for runtime LLM configuration and provider adapters."""

import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import yaml
from fastapi import FastAPI, status
from pydantic import SecretStr

from app.adapters.llm import (
    DeepSeekAdapter,
    GeminiAdapter,
    LLMClientConfig,
    LLMRequest,
    OpenAIAdapter,
)
from app.adapters.llm.errors import (
    LLMConfigurationError,
    LLMProviderError,
    LLMTimeoutError,
)
from app.api.errors import llm_http_exception
from app.api.router import api_router
from app.core.llm_catalog import LLM_PROVIDER_CATALOG
from app.core.settings import (
    LLMProviderSettings,
    LLMSettings,
    Settings,
    load_settings,
)
from app.schemas.llm import LLMConfigRequest, LLMProvider
from app.services.llm_runtime import LLMRuntime
from logs import log


def make_llm_settings() -> LLMSettings:
    """Create provider defaults without reading local environment files."""
    return LLMSettings(
        default_provider=LLMProvider.MOCK,
        timeout_seconds=10,
        max_output_tokens=256,
        openai=LLMProviderSettings(
            model="gpt-5.6-luna",
            base_url="https://api.openai.com/v1",
        ),
        gemini=LLMProviderSettings(
            model="gemini-3.5-flash",
            base_url="https://generativelanguage.googleapis.com/v1beta",
        ),
        deepseek=LLMProviderSettings(
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
        ),
    )


def make_client_config(provider: LLMProvider, base_url: str, model: str) -> LLMClientConfig:
    """Create an adapter config with a non-secret test key."""
    return LLMClientConfig(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=SecretStr("test-key"),
        timeout_seconds=1,
        max_output_tokens=128,
    )


def make_request() -> LLMRequest:
    return LLMRequest(
        request_id="req_test",
        session_id="unity-demo",
        message="Hello",
    )


class LLMRuntimeConfigurationTest(unittest.TestCase):
    """Verify defaults, secret handling, and safe endpoint overrides."""

    def test_provider_only_uses_defaults_and_environment_key(self) -> None:
        runtime = LLMRuntime(make_llm_settings())
        with patch.dict(os.environ, {"OPENAI_API_KEY": "environment-secret"}):
            response = runtime.configure(
                LLMConfigRequest(provider=LLMProvider.OPENAI)
            )

        self.assertEqual(response.model, "gpt-5.6-luna")
        self.assertEqual(response.base_url, "https://api.openai.com/v1")
        self.assertTrue(response.api_key_configured)
        self.assertEqual(response.api_key_source, "environment")
        self.assertNotIn("api_key", response.model_dump())

    def test_request_key_is_not_logged_or_returned(self) -> None:
        runtime = LLMRuntime(make_llm_settings())
        stream = io.StringIO()
        sink_id = log.add(stream, format="{message}")
        try:
            response = runtime.configure(
                LLMConfigRequest(
                    provider=LLMProvider.DEEPSEEK,
                    api_key="request-secret",
                )
            )
            log.complete()
        finally:
            log.remove(sink_id)

        self.assertNotIn("api_key", response.model_dump())
        self.assertNotIn("request-secret", stream.getvalue())

    def test_environment_key_cannot_be_sent_to_custom_base_url(self) -> None:
        runtime = LLMRuntime(make_llm_settings())
        with patch.dict(os.environ, {"OPENAI_API_KEY": "environment-secret"}):
            with self.assertRaises(LLMConfigurationError):
                runtime.configure(
                    LLMConfigRequest(
                        provider=LLMProvider.OPENAI,
                        base_url="https://proxy.example.com/v1",
                    )
                )

    def test_config_example_validates_as_complete_settings(self) -> None:
        config_path = Path(__file__).parents[1] / "config" / "config_example.yaml"
        raw_config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        raw_config["environment"] = "debug"

        settings = Settings.model_validate(raw_config)

        self.assertEqual(settings.llm.default_provider, LLMProvider.MOCK)
        catalog = {item.provider: item for item in LLM_PROVIDER_CATALOG.providers}
        for provider in (
            LLMProvider.OPENAI,
            LLMProvider.GEMINI,
            LLMProvider.DEEPSEEK,
        ):
            defaults = getattr(settings.llm, provider.value)
            self.assertEqual(catalog[provider].default_model, defaults.model)

    def test_docker_config_uses_container_network_settings(self) -> None:
        settings = load_settings("docker")

        self.assertEqual(settings.server.host, "0.0.0.0")
        self.assertFalse(settings.server.reload)
        self.assertEqual(settings.llm.default_provider, LLMProvider.MOCK)


class RuntimeAPIIntegrationTest(unittest.IsolatedAsyncioTestCase):
    """Verify the shared config route updates chat without external calls."""

    async def test_configuration_updates_chat_runtime(self) -> None:
        app = FastAPI()
        app.state.llm_runtime = LLMRuntime(make_llm_settings())
        app.include_router(api_router)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            provider_response = await client.post(
                "/api/v1/llm/config",
                json={"provider": "deepseek", "api_key": "test-key"},
            )
            mock_response = await client.post(
                "/api/v1/llm/config",
                json={"provider": "mock"},
            )
            chat_response = await client.post(
                "/api/v1/unity/chat",
                json={"session_id": "unity-demo", "message": "Hello"},
            )

        self.assertEqual(provider_response.status_code, status.HTTP_200_OK)
        self.assertNotIn("api_key", provider_response.json())
        self.assertEqual(mock_response.json()["provider"], "mock")
        self.assertEqual(chat_response.status_code, status.HTTP_200_OK)
        self.assertEqual(chat_response.json()["reply"], "Echo: Hello")

    async def test_provider_presets_are_valid_config_requests(self) -> None:
        app = FastAPI()
        app.state.llm_runtime = LLMRuntime(make_llm_settings())
        app.include_router(api_router)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/v1/llm/providers")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        providers = response.json()["providers"]
        self.assertEqual(
            {item["provider"] for item in providers},
            {"mock", "openai", "gemini", "deepseek"},
        )
        for provider in providers:
            models = provider["models"]
            self.assertIn(provider["default_model"], {m["model"] for m in models})
            for model in models:
                request = LLMConfigRequest.model_validate(model["config"])
                self.assertEqual(request.provider.value, provider["provider"])
                self.assertEqual(request.model, model["model"])


class ProviderAdapterTest(unittest.IsolatedAsyncioTestCase):
    """Verify provider formats with in-process transports only."""

    async def test_openai_responses_format(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertEqual(request.url.path, "/v1/responses")
            self.assertEqual(request.headers["Authorization"], "Bearer test-key")
            self.assertEqual(payload["model"], "gpt-5.6-luna")
            return httpx.Response(
                200,
                json={
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {"type": "output_text", "text": "OpenAI reply"}
                            ],
                        }
                    ]
                },
            )

        adapter = OpenAIAdapter(
            make_client_config(
                LLMProvider.OPENAI,
                "https://api.openai.com/v1",
                "gpt-5.6-luna",
            ),
            transport=httpx.MockTransport(handler),
        )

        result = await adapter.generate(make_request())

        self.assertEqual(result.text, "OpenAI reply")

    async def test_gemini_generate_content_format(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(
                request.url.path,
                "/v1beta/models/gemini-3.5-flash:generateContent",
            )
            self.assertEqual(request.headers["x-goog-api-key"], "test-key")
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": "Gemini reply"}]}}
                    ]
                },
            )

        adapter = GeminiAdapter(
            make_client_config(
                LLMProvider.GEMINI,
                "https://generativelanguage.googleapis.com/v1beta",
                "gemini-3.5-flash",
            ),
            transport=httpx.MockTransport(handler),
        )

        result = await adapter.generate(make_request())

        self.assertEqual(result.text, "Gemini reply")

    async def test_deepseek_chat_completions_format(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertEqual(request.url.path, "/chat/completions")
            self.assertEqual(payload["model"], "deepseek-v4-flash")
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": "DeepSeek reply"}}
                    ]
                },
            )

        adapter = DeepSeekAdapter(
            make_client_config(
                LLMProvider.DEEPSEEK,
                "https://api.deepseek.com",
                "deepseek-v4-flash",
            ),
            transport=httpx.MockTransport(handler),
        )

        result = await adapter.generate(make_request())

        self.assertEqual(result.text, "DeepSeek reply")

    async def test_timeout_is_converted(self) -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("test timeout", request=request)

        adapter = OpenAIAdapter(
            make_client_config(
                LLMProvider.OPENAI,
                "https://api.openai.com/v1",
                "gpt-5.6-luna",
            ),
            transport=httpx.MockTransport(handler),
        )

        with self.assertRaises(LLMTimeoutError):
            await adapter.generate(make_request())


class LLMHTTPErrorTest(unittest.TestCase):
    """Verify stable HTTP status conversion."""

    def test_timeout_maps_to_gateway_timeout(self) -> None:
        error = llm_http_exception(LLMTimeoutError(LLMProvider.OPENAI))
        self.assertEqual(error.status_code, status.HTTP_504_GATEWAY_TIMEOUT)

    def test_provider_error_maps_to_bad_gateway(self) -> None:
        error = llm_http_exception(
            LLMProviderError(LLMProvider.GEMINI, "provider failed")
        )
        self.assertEqual(error.status_code, status.HTTP_502_BAD_GATEWAY)


if __name__ == "__main__":
    unittest.main()
