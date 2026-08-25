"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes import agents, llm_config, ping, sessions, unity

api_router = APIRouter()
api_router.include_router(ping.router, tags=["health"])
api_router.include_router(unity.router, tags=["unity"])
api_router.include_router(agents.router, prefix="/api/v1", tags=["agents"])
api_router.include_router(sessions.router, prefix="/api/v1", tags=["sessions"])
api_router.include_router(
    llm_config.router,
    prefix="/api/v1",
    tags=["llm"],
)
