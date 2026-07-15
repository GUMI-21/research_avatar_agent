"""Application service for the public chat contract."""

from uuid import uuid4

from app.adapters.llm import LLMClient, LLMRequest
from app.schemas.chat import (
    AvatarAction,
    AvatarCommand,
    ChatRequest,
    ChatResponse,
    EmotionLabel,
    EmotionState,
)


class ChatService:
    """Build stable chat responses from a provider-independent LLM client."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm_client = llm_client

    async def respond(self, request: ChatRequest) -> ChatResponse:
        """Generate a reply while the emotion module remains neutral."""
        request_id = f"req_{uuid4().hex}"
        llm_result = await self._llm_client.generate(
            LLMRequest(
                request_id=request_id,
                session_id=request.session_id,
                message=request.message,
            )
        )
        return ChatResponse(
            request_id=request_id,
            reply=llm_result.text,
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
