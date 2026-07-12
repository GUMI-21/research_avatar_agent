"""Health-check routes."""

from fastapi import APIRouter, Request, status

from app.schemas.health import PingResponse
from logs import log

router = APIRouter()


@router.get(
    "/ping",
    response_model=PingResponse,
    status_code=status.HTTP_200_OK,
)
async def ping(request: Request) -> PingResponse:
    """Return a minimal health response for server startup checks."""
    response = PingResponse(status="ok", service="avatar-agent-server")
    client_ip = request.client.host if request.client else "unknown"
    log.info(
        "Ping request client_ip={} http_status={} service_status={}",
        client_ip,
        status.HTTP_200_OK,
        response.status,
    )
    return response
