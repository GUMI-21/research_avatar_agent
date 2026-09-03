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


class KnowledgeSyncResponse(BaseModel):
    source_id: str
    status: Literal["ready"] = "ready"
    scanned: int
    created: int
    updated: int
    deleted: int
    unchanged: int
    chunks: int


class KnowledgeEmbeddingIndexResponse(BaseModel):
    source_id: str
    provider: str
    model: str
    indexed: int
    unchanged: int


class KnowledgeDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    relative_path: str
    title: str
    content_hash: str
    frontmatter: dict[str, object]
    source_modified_at: datetime
    indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class KnowledgeDocumentListResponse(BaseModel):
    documents: list[KnowledgeDocumentRead]
    next_cursor: str | None
    has_more: bool


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)
    strategy: Literal["keyword", "vector"] = "keyword"

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped


class KnowledgeCitation(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    relative_path: str
    heading_path: list[str]
    snippet: str
    start_line: int
    end_line: int
    retrieval_method: Literal["keyword", "vector"] = "keyword"
    score: float


class KnowledgeSearchResponse(BaseModel):
    source_id: str
    query: str
    strategy: Literal["keyword", "vector"] = "keyword"
    citations: list[KnowledgeCitation]
