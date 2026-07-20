"""Public runtime configuration contracts for LLM providers."""

from enum import Enum
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, SecretStr, field_validator


class LLMProvider(str, Enum):
    """LLM providers supported by the current backend."""

    MOCK = "mock"
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"


class LLMConfigRequest(BaseModel):
    """Runtime provider selection received from Unity or web clients."""

    provider: LLMProvider
    api_key: SecretStr | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1, max_length=256)
    base_url: AnyHttpUrl | None = None

    @field_validator("model")
    @classmethod
    def reject_blank_model(cls, value: str | None) -> str | None:
        """Reject model overrides that contain only whitespace."""
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value


class LLMConfigResponse(BaseModel):
    """Safe runtime configuration summary that never exposes the API key."""

    provider: LLMProvider
    model: str
    base_url: str
    api_key_configured: bool
    api_key_source: Literal["request", "environment", "not_required"]


class LLMConfigPreset(BaseModel):
    """Safe provider/model pair that can be posted to the config endpoint."""

    provider: LLMProvider
    model: str


class LLMModelOption(BaseModel):
    """One model shown in a client selection list."""

    model: str
    display_name: str
    config: LLMConfigPreset


class LLMProviderOption(BaseModel):
    """One provider and its curated model choices."""

    provider: LLMProvider
    display_name: str
    default_model: str
    allow_custom_model: bool
    models: list[LLMModelOption]


class LLMProvidersResponse(BaseModel):
    """Provider catalog shared by Unity and web clients."""

    providers: list[LLMProviderOption]
