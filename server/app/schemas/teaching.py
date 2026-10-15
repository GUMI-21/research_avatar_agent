"""English-led kana course selection and structured model output contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.avatar import AvatarControl

_COURSE_ID = r"^[a-z][a-z0-9_-]{0,63}$"


class CourseSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # IDs resolve through a server-owned catalog, never directly as file paths.
    course_id: str = Field(default="gojuon-en", pattern=_COURSE_ID)
    lesson_id: str = Field(default="hiragana-vowels", pattern=_COURSE_ID)
    instruction_language: Literal["en"] = "en"
    target_language: Literal["ja"] = "ja"


class TeachingTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    schema_version: Literal[1] = 1
    reply: str = Field(min_length=1, max_length=10_000)
    avatar: AvatarControl = Field(default_factory=AvatarControl)
