"""In-memory LLM provider selection shared by API clients."""

import os
from time import perf_counter

from pydantic import SecretStr

from app.adapters.llm import (
    DeepSeekAdapter,
    GeminiAdapter,
    LLMClient,
    LLMClientConfig,
    LLMRequest,
    LLMResult,
    MockLLMAdapter,
    OpenAIAdapter,
)
from app.adapters.llm.errors import LLMConfigurationError, LLMError
from app.core.settings import LLMSettings
from app.schemas.llm import LLMConfigRequest, LLMConfigResponse, LLMProvider
from logs import log

API_KEY_ENVIRONMENTS: dict[LLMProvider, tuple[str, ...]] = {
    LLMProvider.OPENAI: ("OPENAI_API_KEY",),
    LLMProvider.GEMINI: ("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    LLMProvider.DEEPSEEK: ("DEEPSEEK_API_KEY",),
}


class LLMRuntime(LLMClient):
    """Resolve runtime configuration and delegate to the selected adapter."""

    def __init__(self, settings: LLMSettings) -> None:
        self._settings = settings
        self._config = LLMClientConfig(
            provider=LLMProvider.MOCK,
            model="mock-echo",
            base_url="mock://local",
            api_key=None,
            timeout_seconds=settings.timeout_seconds,
            max_output_tokens=settings.max_output_tokens,
        )
        self._api_key_source = "not_required"
        if settings.default_provider is not LLMProvider.MOCK:
            self.configure(LLMConfigRequest(provider=settings.default_provider))

    def configure(self, request: LLMConfigRequest) -> LLMConfigResponse:
        """Atomically replace the active in-memory provider configuration."""
        if request.provider is LLMProvider.MOCK:
            self._config = LLMClientConfig(
                provider=LLMProvider.MOCK,
                model="mock-echo",
                base_url="mock://local",
                api_key=None,
                timeout_seconds=self._settings.timeout_seconds,
                max_output_tokens=self._settings.max_output_tokens,
            )
            self._api_key_source = "not_required"
            return self.current_config()

        defaults = getattr(self._settings, request.provider.value)
        api_key, api_key_source = self._resolve_api_key(request)
        base_url = str(request.base_url or defaults.base_url).rstrip("/")
        default_base_url = str(defaults.base_url).rstrip("/")
        if api_key_source == "environment" and base_url != default_base_url:
            raise LLMConfigurationError(
                "Custom base_url requires api_key in the same request"
            )
        model = request.model.strip() if request.model else defaults.model

        self._config = LLMClientConfig(
            provider=request.provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=self._settings.timeout_seconds,
            max_output_tokens=self._settings.max_output_tokens,
        )
        self._api_key_source = api_key_source
        log.info(
            "LLM configured provider={} model={} base_url={} api_key_source={}",
            request.provider.value,
            model,
            base_url,
            api_key_source,
        )
        return self.current_config()

    def current_config(self) -> LLMConfigResponse:
        """Return a safe summary without exposing the active secret."""
        return LLMConfigResponse(
            provider=self._config.provider,
            model=self._config.model,
            base_url=self._config.base_url,
            api_key_configured=self._config.api_key is not None,
            api_key_source=self._api_key_source,
        )

    async def generate(self, request: LLMRequest) -> LLMResult:
        """Generate text with the provider active at the start of this call."""
        config = self._config
        adapter = self._build_adapter(config)
        started_at = perf_counter()
        try:
            result = await adapter.generate(request)
        except LLMError as error:
            elapsed_ms = int((perf_counter() - started_at) * 1000)
            log.warning(
                "LLM request failed request_id={} provider={} model={} "
                "elapsed_ms={} error_type={}",
                request.request_id,
                config.provider.value,
                config.model,
                elapsed_ms,
                type(error).__name__,
            )
            raise

        elapsed_ms = int((perf_counter() - started_at) * 1000)
        log.info(
            "LLM request completed request_id={} provider={} model={} elapsed_ms={}",
            request.request_id,
            config.provider.value,
            config.model,
            elapsed_ms,
        )
        return result

    def _resolve_api_key(
        self, request: LLMConfigRequest
    ) -> tuple[SecretStr, str]:
        if request.api_key is not None:
            return request.api_key, "request"

        for environment_name in API_KEY_ENVIRONMENTS[request.provider]:
            value = os.getenv(environment_name)
            if value:
                return SecretStr(value), "environment"

        environment_names = " or ".join(API_KEY_ENVIRONMENTS[request.provider])
        raise LLMConfigurationError(
            f"API key is required; send api_key or set {environment_names}"
        )

    @staticmethod
    def _build_adapter(config: LLMClientConfig) -> LLMClient:
        if config.provider is LLMProvider.MOCK:
            return MockLLMAdapter()
        if config.provider is LLMProvider.OPENAI:
            return OpenAIAdapter(config)
        if config.provider is LLMProvider.GEMINI:
            return GeminiAdapter(config)
        if config.provider is LLMProvider.DEEPSEEK:
            return DeepSeekAdapter(config)
        raise LLMConfigurationError(
            f"Unsupported provider: {config.provider.value}"
        )
