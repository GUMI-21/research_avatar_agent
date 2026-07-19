"""Validated server settings loaded from an environment YAML file."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal, Tuple

import yaml
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from app.schemas.llm import LLMProvider

EnvironmentName = Literal["debug", "prod", "docker"]
SUPPORTED_ENVIRONMENTS: Tuple[str, ...] = ("debug", "prod", "docker")
SERVER_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = SERVER_ROOT / "config"


class StrictSettingsModel(BaseModel):
    """Reject unknown configuration keys to catch misspellings early."""

    model_config = ConfigDict(extra="forbid")


class AppSettings(StrictSettingsModel):
    """Application identity shown in API documentation and logs."""

    name: str
    description: str
    version: str


class ServerSettings(StrictSettingsModel):
    """Uvicorn network and development settings."""

    host: str
    port: int = Field(ge=1, le=65535)
    reload: bool


class LoggingSettings(StrictSettingsModel):
    """Loguru console and rotating-file settings."""

    level: str
    directory: Path
    file_name: str
    rotation: str
    retention: str
    compression: str
    console: bool


class LLMProviderSettings(StrictSettingsModel):
    """Default model and endpoint for one cloud provider."""

    model: str = Field(min_length=1, max_length=256)
    base_url: AnyHttpUrl


class LLMSettings(StrictSettingsModel):
    """Provider-independent defaults for runtime LLM selection."""

    default_provider: LLMProvider
    timeout_seconds: float = Field(gt=0.0, le=300.0)
    max_output_tokens: int = Field(ge=1, le=131_072)
    openai: LLMProviderSettings
    gemini: LLMProviderSettings
    deepseek: LLMProviderSettings


class Settings(StrictSettingsModel):
    """Complete server configuration for one runtime environment."""

    environment: EnvironmentName
    app: AppSettings
    server: ServerSettings
    logging: LoggingSettings
    llm: LLMSettings


def load_settings(environment: str) -> Settings:
    """Load and validate config/<environment>.yaml."""
    if environment not in SUPPORTED_ENVIRONMENTS:
        supported = ", ".join(SUPPORTED_ENVIRONMENTS)
        raise ValueError(f"Unsupported environment '{environment}'; use {supported}")

    config_path = CONFIG_DIR / f"{environment}.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"Missing config file: {config_path}. "
            "Copy config/config_example.yaml and customize it first."
        )

    with config_path.open(encoding="utf-8") as config_file:
        raw_config = yaml.safe_load(config_file)

    if not isinstance(raw_config, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {config_path}")

    raw_config["environment"] = environment
    return Settings.model_validate(raw_config)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return settings selected by the startup entrypoint."""
    environment = os.getenv("APP_ENV")
    if environment is None:
        raise RuntimeError(
            "APP_ENV is not set; start with "
            "'python run_avatar_server.py --env debug' or '--env prod'"
        )
    return load_settings(environment)
