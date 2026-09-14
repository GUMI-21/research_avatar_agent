"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver

from app.adapters.agent import CodexAgentRuntime, NativeAgentRuntime
from app.adapters.knowledge import FastEmbedAdapter
from app.api.router import api_router
from app.core.database import Database
from app.core.settings import Settings, get_settings
from app.services.llm_credentials import LLMCredentialStore
from app.services.llm_runtime import LLMRuntime
from app.services.runtime_registry import RuntimeRegistry
from app.tools import ToolApprovalBroker, create_file_tool_registry
from logs import configure_logging, log


@asynccontextmanager # 异步协程，由“异步生成器”实现的生命周期上下文。
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Record the server process lifecycle."""
    await app.state.llm_credentials.restore(app.state.llm_runtime)
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
    # langGraph检查点存储器,所有请求共享同一个实例。 进程内字典
    app.state.graph_checkpointer = InMemorySaver()
    app.state.embedding_client = FastEmbedAdapter(
        model=settings.embedding.model,
        dimensions=settings.embedding.dimensions,
        cache_dir=settings.embedding.cache_dir,
    )
    llm_runtime = LLMRuntime(settings.llm)
    app.state.llm_credentials = LLMCredentialStore(
        app.state.database, settings.llm.credential_key_path
    )
    runtime_registry = RuntimeRegistry()
    file_tools = create_file_tool_registry()
    approvals = ToolApprovalBroker()
    app.state.tool_approval_broker = approvals
    # 注册创建 NativeAgentRuntime 的匿名工厂函数
    runtime_registry.register(
        "native", lambda: NativeAgentRuntime(llm_runtime, file_tools, approvals)
    )
    runtime_registry.register(
        "codex", lambda: CodexAgentRuntime(
            settings.codex.workspace_root,
            executable=settings.codex.executable,
            timeout_seconds=settings.codex.timeout_seconds,
        )
    )
    app.state.llm_runtime = llm_runtime
    app.state.runtime_registry = runtime_registry
    app.include_router(api_router)
    return app


settings = get_settings()
configure_logging(settings.logging)
app = create_app(settings)
