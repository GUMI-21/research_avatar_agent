"""Workspace identity API contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

USERNAME_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$"


class WorkspaceCreate(BaseModel):
    username: str = Field(min_length=1, max_length=64, pattern=USERNAME_PATTERN)

    @field_validator("username", mode="before")
    @classmethod
    def normalize_username(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    created_at: datetime
