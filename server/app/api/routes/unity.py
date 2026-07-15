"""HTTP routes consumed by the Unity avatar client."""

from fastapi import APIRouter, Depends, Request, status

from app.adapters.llm.errors import LLMError
from app.api.dependencies import get_llm_runtime
from app.api.errors import llm_http_exception
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat import ChatService
from app.services.llm_runtime import LLMRuntime
from logs import log

router = APIRouter(prefix="/api/v1/unity")


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(
    http_request: Request,
    chat_request: ChatRequest,
    llm_runtime: LLMRuntime = Depends(get_llm_runtime),
) -> ChatResponse:
    """Return an LLM reply that follows the stable client contract."""
    try:
        response = await ChatService(llm_runtime).respond(chat_request)
    except LLMError as error:
        raise llm_http_exception(error) from error
    client_ip = http_request.client.host if http_request.client else "unknown"
    log.info(
        "Chat request request_id={} session_id={} client_ip={} http_status={}",
        response.request_id,
        chat_request.session_id,
        client_ip,
        status.HTTP_200_OK,
    )
    return response
