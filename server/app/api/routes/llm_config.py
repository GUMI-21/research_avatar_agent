"""Client-scoped runtime LLM configuration endpoint."""

from fastapi import APIRouter, Depends, Request, status

from app.adapters.llm.errors import LLMConfigurationError
from app.api.dependencies import ClientID, get_llm_runtime
from app.api.errors import llm_http_exception
from app.core.llm_catalog import LLM_PROVIDER_CATALOG
from app.schemas.llm import (
    LLMConfigRequest,
    LLMConfigResponse,
    LLMProvidersResponse,
)
from app.services.llm_runtime import LLMRuntime

router = APIRouter()


@router.get("/llm/providers", response_model=LLMProvidersResponse)
async def list_llm_providers() -> LLMProvidersResponse:
    """Return safe presets that clients can post to the config endpoint."""
    return LLM_PROVIDER_CATALOG


@router.get("/llm/config", response_model=LLMConfigResponse)
async def get_llm_config(
    client_id: ClientID,
    llm_runtime: LLMRuntime = Depends(get_llm_runtime),
) -> LLMConfigResponse:
    """Return the active runtime selection without exposing its API key."""
    return llm_runtime.current_config(client_id)

@router.post(
    "/llm/config",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def configure_llm(
    config_request: LLMConfigRequest,
    client_id: ClientID,
    http_request: Request,
    llm_runtime: LLMRuntime = Depends(get_llm_runtime),
) -> LLMConfigResponse:
    """Select and persist a provider without returning its API key."""
    try:
        response = llm_runtime.configure(config_request, client_id)
        credentials = getattr(http_request.app.state, "llm_credentials", None)
        if credentials is not None:
            await credentials.save(client_id, config_request, response)
        return response
    except LLMConfigurationError as error:
        raise llm_http_exception(error) from error
