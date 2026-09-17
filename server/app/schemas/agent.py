"""Public request and response contracts for workspace Agents."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.llm import LLMProvider


# request 字段
class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    avatar_emoji: str = Field(default="🤖", min_length=1, max_length=16)
    system_prompt: str = Field(min_length=1, max_length=50_000)
    runtime: str = Field(default="native", min_length=1, max_length=64)
    provider: LLMProvider | None = None
    model: str | None = Field(default=None, min_length=1, max_length=128)
    workspace_path: str | None = Field(
        default=None, min_length=1, max_length=1024
    )
    knowledge_source_ids: list[str] = Field(default_factory=list, max_length=20)

    @field_validator(
        "name", "runtime", "model", "avatar_emoji", "workspace_path"
    )
    @classmethod
    def strip_short_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @model_validator(mode="after")
    def validate_runtime_workspace(self) -> "AgentCreate":
        if self.workspace_path is not None and self.runtime != "codex":
            raise ValueError("workspace_path requires the codex runtime")
        return self

    @field_validator("system_prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @field_validator("knowledge_source_ids")
    @classmethod
    def validate_source_ids(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 36 for value in normalized):
            raise ValueError("knowledge source id is invalid")
        if len(normalized) != len(set(normalized)):
            raise ValueError("knowledge source ids must be unique")
        return normalized


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_emoji: str | None = Field(default=None, min_length=1, max_length=16)
    system_prompt: str | None = Field(default=None, min_length=1, max_length=50_000)
    provider: LLMProvider | None = None
    model: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("name", "system_prompt", "model", "avatar_emoji")
    @classmethod
    def reject_blank_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be blank")
        return value.strip() if value is not None else None


# response 字段
class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    name: str
    avatar_emoji: str
    system_prompt: str
    runtime: str
    provider: LLMProvider | None
    model: str | None
    workspace_path: str | None
    knowledge_source_ids: list[str]
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    agents: list[AgentRead]
