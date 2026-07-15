"""Shared runtime LLM configuration endpoint."""

from fastapi import APIRouter, Depends, status

from app.adapters.llm.errors import LLMConfigurationError
from app.api.dependencies import get_llm_runtime
from app.api.errors import llm_http_exception
from app.schemas.llm import LLMConfigRequest, LLMConfigResponse
from app.services.llm_runtime import LLMRuntime

router = APIRouter()


@router.post(
    "/llm/config",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def configure_llm(
    config_request: LLMConfigRequest,
    llm_runtime: LLMRuntime = Depends(get_llm_runtime),
) -> LLMConfigResponse:
    """Select a provider without persisting or returning its API key."""
    try:
        return llm_runtime.configure(config_request)
    except LLMConfigurationError as error:
        raise llm_http_exception(error) from error
