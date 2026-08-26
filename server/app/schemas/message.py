"""Public response contracts for conversation Messages."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    session_id: str
    agent_id: str
    run_id: str | None
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    sequence: int
    created_at: datetime


class MessageListResponse(BaseModel):
    messages: list[MessageRead]
    next_cursor: int | None
    has_more: bool
