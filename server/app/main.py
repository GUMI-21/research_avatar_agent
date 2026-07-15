"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.core.settings import Settings, get_settings
from app.services.llm_runtime import LLMRuntime
from logs import configure_logging, log


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Record the server process lifecycle."""
    log.info(
        "Starting {} version {} environment={}",
        app.title,
        app.version,
        app.state.settings.environment,
    )
    try:
        yield
    finally:
        log.info("Stopping {}", app.title)


def create_app(settings: Settings) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title=settings.app.name,
        description=settings.app.description,
        version=settings.app.version,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.llm_runtime = LLMRuntime(settings.llm)
    app.include_router(api_router)
    return app


settings = get_settings()
configure_logging(settings.logging)
app = create_app(settings)
