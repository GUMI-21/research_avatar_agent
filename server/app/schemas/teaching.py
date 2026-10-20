"""English-led kana course selection and structured model output contracts."""

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.avatar import AvatarControl

_COURSE_ID = r"^[a-z][a-z0-9_-]{0,63}$"


class CourseSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # IDs resolve through a server-owned catalog, never directly as file paths.
    course_id: str = Field(default="gojuon-en", pattern=_COURSE_ID)
    lesson_id: str = Field(default="hiragana-vowels", pattern=_COURSE_ID)
    instruction_language: Literal["en"] = "en"
    target_language: Literal["ja"] = "ja"


class CourseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    lesson_ids: tuple[str, ...]
    version_hash: str
    instruction_language: Literal["en"]
    target_language: Literal["ja"]


class CourseListResponse(BaseModel):
    courses: list[CourseRead]


class TeachingSessionRead(CourseSelection):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    session_id: str
    course_version: str
    completed_turns: int
    state_version: int
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        # 写入使用 utc_now；SQLite 读回无时区，避免创建/查询响应格式不同。
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class TeachingTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal[1] = 1
    reply: str = Field(min_length=1, max_length=10_000)
    avatar: AvatarControl = Field(default_factory=AvatarControl)
