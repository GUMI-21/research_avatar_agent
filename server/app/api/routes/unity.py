"""HTTP routes consumed by the Unity avatar client."""

from fastapi import APIRouter, Request, status

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService
from logs import log

router = APIRouter(prefix="/api/v1/unity")
chat_service = ChatService()


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(http_request: Request, chat_request: ChatRequest) -> ChatResponse:
    """Return a placeholder chat response that follows the stable client contract."""
    response = await chat_service.respond(chat_request)
    client_ip = http_request.client.host if http_request.client else "unknown"
    log.info(
        "Chat request request_id={} session_id={} client_ip={} http_status={}",
        response.request_id,
        chat_request.session_id,
        client_ip,
        status.HTTP_200_OK,
    )
    return response
