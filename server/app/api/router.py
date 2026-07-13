"""Top-level API router."""

from fastapi import APIRouter

from app.api.routes import ping, unity

api_router = APIRouter()
api_router.include_router(ping.router, tags=["health"])
api_router.include_router(unity.router, tags=["unity"])
