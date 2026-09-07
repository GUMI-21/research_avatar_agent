"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes import (
    agents,
    knowledge,
    llm_config,
    messages,
    ping,
    sessions,
    unity,
    usage,
    workspace_ws,
)

api_router = APIRouter()
api_router.include_router(ping.router, tags=["health"])
api_router.include_router(unity.router, tags=["unity"])
api_router.include_router(agents.router, prefix="/api/v1", tags=["agents"])
api_router.include_router(knowledge.router, prefix="/api/v1", tags=["knowledge"])
api_router.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
api_router.include_router(messages.router, prefix="/api/v1", tags=["messages"])
api_router.include_router(usage.router, prefix="/api/v1", tags=["usage"])
api_router.include_router(workspace_ws.router, prefix="/api/v1", tags=["runs"])
api_router.include_router(
    llm_config.router,
    prefix="/api/v1",
    tags=["llm"],
)
