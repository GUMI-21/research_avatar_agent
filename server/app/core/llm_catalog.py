"""Client-facing LLM provider and model presets."""

from app.schemas.llm import (
    LLMConfigPreset,
    LLMModelOption,
    LLMProvider,
    LLMProviderOption,
    LLMProvidersResponse,
)


def _provider(
    provider: LLMProvider,
    display_name: str,
    default_model: str,
    models: tuple[tuple[str, str], ...],
    *,
    allow_custom_model: bool = True,
) -> LLMProviderOption:
    return LLMProviderOption(
        provider=provider,
        display_name=display_name,
        default_model=default_model,
        allow_custom_model=allow_custom_model,
        models=[
            LLMModelOption(
                model=model,
                display_name=model_name,
                config=LLMConfigPreset(provider=provider, model=model),
            )
            for model, model_name in models
        ],
    )


LLM_PROVIDER_CATALOG = LLMProvidersResponse(
    providers=[
        _provider(
            LLMProvider.MOCK,
            "Mock",
            "mock-echo",
            (("mock-echo", "Mock Echo"),),
            allow_custom_model=False,
        ),
        _provider(
            LLMProvider.OPENAI,
            "OpenAI",
            "gpt-5.6-luna",
            (
                ("gpt-5.6-luna", "GPT-5.6 Luna"),
                ("gpt-5.6-terra", "GPT-5.6 Terra"),
                ("gpt-5.6-sol", "GPT-5.6 Sol"),
            ),
        ),
        _provider(
            LLMProvider.GEMINI,
            "Gemini",
            "gemini-3.5-flash",
            (
                ("gemini-3.5-flash", "Gemini 3.5 Flash"),
                ("gemini-2.5-flash", "Gemini 2.5 Flash"),
                ("gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite"),
            ),
        ),
        _provider(
            LLMProvider.DEEPSEEK,
            "DeepSeek",
            "deepseek-v4-flash",
            (
                ("deepseek-v4-flash", "DeepSeek V4 Flash"),
                ("deepseek-v4-pro", "DeepSeek V4 Pro"),
            ),
        ),
    ]
)
