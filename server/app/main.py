"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.adapters.agent import NativeAgentRuntime
from app.api.router import api_router
from app.core.database import Database
from app.core.settings import Settings, get_settings
from app.services.llm_runtime import LLMRuntime
from app.services.runtime_registry import RuntimeRegistry
from logs import configure_logging, log


@asynccontextmanager # 异步协程，由“异步生成器”实现的生命周期上下文。
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
        await app.state.database.dispose()
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
    app.state.database = Database(settings.database.url)
    llm_runtime = LLMRuntime(settings.llm)
    runtime_registry = RuntimeRegistry()
    runtime_registry.register("native", lambda: NativeAgentRuntime(llm_runtime))
    app.state.llm_runtime = llm_runtime
    app.state.runtime_registry = runtime_registry
    app.include_router(api_router)
    return app


settings = get_settings()
configure_logging(settings.logging)
app = create_app(settings)
