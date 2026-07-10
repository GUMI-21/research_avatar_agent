"""FastAPI application entrypoint."""

from fastapi import FastAPI

from app.api.router import api_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Avatar Agent Server",
        description="Backend service for the personal AI workspace and avatar assistant.",
        version="0.1.0",
    )
    app.include_router(api_router)
    return app


app = create_app()

