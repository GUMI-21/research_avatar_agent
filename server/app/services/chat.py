"""Application service for the current chat contract placeholder."""

from uuid import uuid4

from app.schemas.chat import (
    AvatarAction,
    AvatarCommand,
    ChatRequest,
    ChatResponse,
    EmotionLabel,
    EmotionState,
)


class ChatService:
    """Build chat responses until the LLM adapter is connected."""

    async def respond(self, request: ChatRequest) -> ChatResponse:
        """Echo the user message with neutral avatar state."""
        return ChatResponse(
            request_id=f"req_{uuid4().hex}",
            reply=f"Echo: {request.message}",
            emotion=EmotionState(
                label=EmotionLabel.NEUTRAL,
                valence=0.0,
                arousal=0.0,
                intensity=0.0,
            ),
            avatar=AvatarCommand(
                expression=EmotionLabel.NEUTRAL,
                action=AvatarAction.IDLE,
                intensity=0.0,
                duration_ms=0,
            ),
        )
