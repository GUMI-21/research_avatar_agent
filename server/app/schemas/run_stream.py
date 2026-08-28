"""WebSocket commands and public Agent Run event frames."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.adapters.agent import RuntimeEventType


class SendMessageCommand(BaseModel):
    type: Literal["send_message"]
    session_id: str = Field(min_length=1, max_length=36)
    content: str = Field(min_length=1, max_length=20_000)

    @field_validator("session_id", "content")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

# 服务端发送给 WebSocket 客户端的统一消息外壳
class RunEventFrame(BaseModel):
    type: RuntimeEventType
    run_id: str
    sequence: int | None  # Run 内持久化事件序号；非持久化事件为 None
    payload: dict[str, object]  # 当前事件的具体数据


class WebSocketErrorFrame(BaseModel):
    type: Literal["error"] = "error"
    code: str
    message: str
