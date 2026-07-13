"""Public chat API request and response contracts."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class EmotionLabel(str, Enum):
    """Emotion labels supported by the first avatar protocol."""

    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    RELAXED = "relaxed"
    SURPRISED = "surprised"


class AvatarAction(str, Enum):
    """Avatar actions supported by the first Unity demo."""

    IDLE = "idle"
    NOD = "nod"
    WAVE = "wave"


class ChatRequest(BaseModel):
    """A single user message sent by a client."""

    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=10_000)

    @field_validator("session_id", "message")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        """Reject values that contain only whitespace."""
        if not value.strip():
            raise ValueError("must not be blank")
        return value


class EmotionState(BaseModel):
    """Normalized affect values exposed to clients."""

    label: EmotionLabel
    valence: float = Field(ge=-1.0, le=1.0)
    arousal: float = Field(ge=0.0, le=1.0)
    intensity: float = Field(ge=0.0, le=1.0)


class AvatarCommand(BaseModel):
    """Semantic expression and action command for an avatar client."""

    expression: EmotionLabel
    action: AvatarAction
    intensity: float = Field(ge=0.0, le=1.0)
    duration_ms: int = Field(ge=0, le=60_000)


class ChatResponse(BaseModel):
    """Stable response returned to Unity and future workspace clients."""

    request_id: str
    reply: str
    emotion: EmotionState
    avatar: AvatarCommand
