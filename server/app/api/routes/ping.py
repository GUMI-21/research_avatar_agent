"""Health-check routes."""

from fastapi import APIRouter

from app.schemas.health import PingResponse

router = APIRouter()


@router.get("/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    """Return a minimal health response for server startup checks."""
    return PingResponse(status="ok", service="avatar-agent-server")

