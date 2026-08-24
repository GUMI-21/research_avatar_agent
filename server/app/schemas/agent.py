"""Public request and response contracts for workspace Agents."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# request 字段
class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    system_prompt: str = Field(min_length=1, max_length=50_000)
    runtime: str = Field(default="native", min_length=1, max_length=64)
    model: str | None = Field(default=None, min_length=1, max_length=128)

    # 校验三个字段
    @field_validator("name", "runtime", "model")
    @classmethod
    def strip_short_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    @field_validator("system_prompt")
    @classmethod
    def reject_blank_prompt(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

# response 字段
class AgentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    name: str
    system_prompt: str
    runtime: str
    model: str | None
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    agents: list[AgentRead]
