"""Read-only runtime safety policy."""

from fastapi import APIRouter, Request

from app.api.dependencies import ClientID
from app.schemas.runtime import MCPStatusResponse, RuntimePolicyResponse

router = APIRouter(prefix="/runtime")


@router.get("/policy", response_model=RuntimePolicyResponse)
async def get_runtime_policy(
    request: Request, client_id: ClientID,
) -> RuntimePolicyResponse:
    del client_id
    return RuntimePolicyResponse(
        demo_mode=bool(request.app.state.demo_mode),
        blocked_tool_risks=request.app.state.blocked_tool_risks,
    )


@router.get("/mcp-status", response_model=MCPStatusResponse)
async def get_mcp_status(
    request: Request, client_id: ClientID,
) -> MCPStatusResponse:
    del client_id
    return MCPStatusResponse(servers=list(request.app.state.mcp_statuses.values()))
