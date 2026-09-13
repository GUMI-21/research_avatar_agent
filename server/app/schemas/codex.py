"""Safe Codex CLI status returned to the web workspace."""

from pydantic import BaseModel, Field


class CodexRateLimitWindow(BaseModel):
    name: str
    used_percent: int = Field(ge=0, le=100)
    window_minutes: int | None
    resets_at: int | None


class CodexStatusResponse(BaseModel):
    installed: bool
    authenticated: bool
    auth_mode: str | None
    plan_type: str | None
    windows: list[CodexRateLimitWindow]
    error: str | None
