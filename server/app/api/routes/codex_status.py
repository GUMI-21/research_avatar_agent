"""Codex CLI login and account limit status."""

from fastapi import APIRouter, Request

from app.api.dependencies import ClientID
from app.schemas.codex import CodexStatusResponse
from app.services.codex_status import CodexStatusService

router = APIRouter()


@router.get("/codex/status", response_model=CodexStatusResponse)
async def get_codex_status(
    client_id: ClientID, request: Request,
) -> CodexStatusResponse:
    """Return server-wide Codex status without exposing account identity."""
    del client_id
    settings = request.app.state.settings
    result = await CodexStatusService(
        settings.codex.executable,
        min(settings.codex.timeout_seconds, 10),
    ).read()
    return CodexStatusResponse.model_validate(result)
