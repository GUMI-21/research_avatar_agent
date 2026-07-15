"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes import llm_config, ping, unity

api_router = APIRouter()
api_router.include_router(ping.router, tags=["health"])
api_router.include_router(unity.router, tags=["unity"])
api_router.include_router(
    llm_config.router,
    prefix="/api/v1",
    tags=["llm"],
)
