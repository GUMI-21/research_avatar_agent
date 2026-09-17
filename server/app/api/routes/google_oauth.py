"""Client-scoped Google OAuth authorization endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.api.dependencies import ClientID
from app.schemas.google_oauth import (
    GoogleOAuthCallbackResponse,
    GoogleOAuthConnectionResponse,
    GoogleOAuthStartResponse,
)
from app.services.google_oauth_flow import GoogleOAuthFlow, GoogleOAuthFlowError

router = APIRouter()


def get_google_oauth_flow(request: Request) -> GoogleOAuthFlow:
    flow = getattr(request.app.state, "google_oauth_flow", None)
    if flow is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured",
        )
    return flow


@router.post("/google/oauth/start", response_model=GoogleOAuthStartResponse)
async def start_google_oauth(
    client_id: ClientID,
    flow: GoogleOAuthFlow = Depends(get_google_oauth_flow),
) -> GoogleOAuthStartResponse:
    return GoogleOAuthStartResponse(authorization_url=flow.start(client_id))


@router.get("/google/oauth/callback", response_model=GoogleOAuthCallbackResponse)
async def complete_google_oauth(
    state_value: Annotated[str, Query(alias="state", min_length=16)],
    code: Annotated[str, Query(min_length=1)],
    flow: GoogleOAuthFlow = Depends(get_google_oauth_flow),
) -> GoogleOAuthCallbackResponse:
    try:
        await flow.complete(state_value, code)
        return GoogleOAuthCallbackResponse()
    except GoogleOAuthFlowError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error


@router.get("/google/oauth/status", response_model=GoogleOAuthConnectionResponse)
async def get_google_oauth_status(
    client_id: ClientID,
    flow: GoogleOAuthFlow = Depends(get_google_oauth_flow),
) -> GoogleOAuthConnectionResponse:
    credential = await flow.connection(client_id)
    if credential is None:
        return GoogleOAuthConnectionResponse(connected=False)
    return GoogleOAuthConnectionResponse(
        connected=True,
        account_email=credential.account_email,
        scopes=credential.scopes,
    )


@router.delete(
    "/google/oauth/connection", response_model=GoogleOAuthConnectionResponse
)
async def disconnect_google_oauth(
    client_id: ClientID,
    flow: GoogleOAuthFlow = Depends(get_google_oauth_flow),
) -> GoogleOAuthConnectionResponse:
    try:
        await flow.disconnect(client_id)
        return GoogleOAuthConnectionResponse(connected=False)
    except GoogleOAuthFlowError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)
        ) from error