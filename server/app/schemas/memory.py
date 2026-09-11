"""Public contracts for lightweight Agent long-term memory."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4_000)

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class MemoryUpdate(BaseModel):
    enabled: bool


class MemoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    content: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class MemoryListResponse(BaseModel):
    memories: list[MemoryRead]
