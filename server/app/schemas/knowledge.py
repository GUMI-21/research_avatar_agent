"""Public contracts for local knowledge sources."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KnowledgeSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    root_path: str = Field(min_length=1, max_length=2048)
    source_type: Literal["obsidian", "markdown"] = "obsidian"

    @field_validator("name", "root_path")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class KnowledgeSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    name: str
    source_type: Literal["obsidian", "markdown"]
    root_path: str
    sync_status: Literal["pending", "syncing", "ready", "failed"]
    error_message: str | None
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeSourceListResponse(BaseModel):
    sources: list[KnowledgeSourceRead]
