"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from os import getenv

from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import SecretStr

from app.adapters.agent import CodexAgentRuntime, NativeAgentRuntime
from app.adapters.knowledge import FastEmbedAdapter
from app.api.router import api_router
from app.core.database import Database
from app.core.settings import Settings, get_settings
from app.services.google_api_client import GoogleAPIClient
from app.services.google_oauth_credentials import GoogleOAuthCredentialStore
from app.services.google_oauth_flow import GoogleOAuthFlow
from app.services.llm_credentials import LLMCredentialStore
from app.services.llm_runtime import LLMRuntime
from app.services.runtime_registry import RuntimeRegistry
from app.services.skills import SkillCatalog
from app.tools import (
    MCPClient, StdioMCPTransport, StreamableHttpMCPTransport,
    ToolApprovalBroker, create_file_tool_registry,
    register_google_read_tools,
    ToolRisk,
)
from logs import configure_logging, log


def _mark_mcp_unavailable(
    app: FastAPI, transport: str, name: str, error: Exception,
) -> None:
    status = app.state.mcp_statuses[(transport, name)]
    status["status"] = "unavailable"
    # Upstream messages may contain private data; expose only the class name.
    status["error_type"] = type(error.__cause__ or error).__name__


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
    mcp_stack = AsyncExitStack()
    try:
        for config in app.state.settings.mcp.stdio_servers:
            try:
                transport = await mcp_stack.enter_async_context(StdioMCPTransport(
                    config.command, config.args, cwd=config.cwd,
                    timeout_seconds=config.timeout_seconds,
                ))
                names = await MCPClient(
                    config.name, transport, config.allowed_domains, config.blocked_tools,
                    on_transport_error=lambda error, name=config.name: (
                        _mark_mcp_unavailable(app, "stdio", name, error)
                    ),
                ).register_tools(
                    app.state.tool_registry
                )
                app.state.mcp_statuses[("stdio", config.name)] = {
                    "name": config.name, "transport": "stdio",
                    "status": "connected", "tool_count": len(names),
                    "error_type": None,
                }
                log.info("Connected MCP server={} tools={}", config.name, len(names))
            except Exception as error:
                app.state.mcp_statuses[("stdio", config.name)] = {
                    "name": config.name, "transport": "stdio",
                    "status": "unavailable", "tool_count": 0,
                    "error_type": type(error).__name__,
                }
                log.warning("MCP server={} unavailable error_type={}",
                            config.name, type(error).__name__)
        for config in app.state.settings.mcp.http_servers:
            try:
                transport = await mcp_stack.enter_async_context(
                    StreamableHttpMCPTransport(
                        str(config.url), timeout_seconds=config.timeout_seconds,
                    )
                )
                names = await MCPClient(
                    config.name, transport, config.allowed_domains, config.blocked_tools,
                    on_transport_error=lambda error, name=config.name: (
                        _mark_mcp_unavailable(app, "http", name, error)
                    ),
                ).register_tools(
                    app.state.tool_registry
                )
                app.state.mcp_statuses[("http", config.name)] = {
                    "name": config.name, "transport": "http",
                    "status": "connected", "tool_count": len(names),
                    "error_type": None,
                }
                log.info("Connected MCP server={} tools={}", config.name, len(names))
            except Exception as error:
                app.state.mcp_statuses[("http", config.name)] = {
                    "name": config.name, "transport": "http",
                    "status": "unavailable", "tool_count": 0,
                    "error_type": type(error).__name__,
                }
                log.warning("MCP server={} unavailable error_type={}",
                            config.name, type(error).__name__)
        yield
    finally:
        await mcp_stack.aclose()
        if app.state.google_api_client is not None:
            await app.state.google_api_client.close()
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
    app.state.mcp_statuses = {
        **{
            ("stdio", config.name): {
                "name": config.name, "transport": "stdio", "status": "pending",
            }
            for config in settings.mcp.stdio_servers
        },
        **{
            ("http", config.name): {
                "name": config.name, "transport": "http", "status": "pending",
            }
            for config in settings.mcp.http_servers
        },
    }
    app.state.database = Database(settings.database.url)
    app.state.skill_catalog = SkillCatalog(
        settings.skills.directories, settings.skills.max_file_bytes
    )
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
    app.state.google_oauth_credentials = GoogleOAuthCredentialStore(
        app.state.database, settings.llm.credential_key_path
    )
    oauth_client_id = getenv("GOOGLE_OAUTH_CLIENT_ID")
    oauth_client_secret = getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    app.state.google_oauth_flow = (
        GoogleOAuthFlow(
            app.state.google_oauth_credentials,
            oauth_client_id,
            SecretStr(oauth_client_secret),
            getenv(
                "GOOGLE_OAUTH_REDIRECT_URI",
                "http://127.0.0.1:8000/api/v1/google/oauth/callback",
            ),
        )
        if oauth_client_id and oauth_client_secret
        else None
    )
    app.state.google_api_client = (
        GoogleAPIClient(
            app.state.google_oauth_credentials,
            oauth_client_id,
            SecretStr(oauth_client_secret),
        )
        if oauth_client_id and oauth_client_secret
        else None
    )
    runtime_registry = RuntimeRegistry()
    blocked_risks = (
        (ToolRisk.LOCAL_WRITE, ToolRisk.EXTERNAL_WRITE)
        if settings.demo.enabled else ()
    )
    file_tools = create_file_tool_registry(blocked_risks=blocked_risks)
    app.state.demo_mode = settings.demo.enabled
    app.state.blocked_tool_risks = tuple(risk.value for risk in blocked_risks)
    if app.state.google_api_client is not None:
        register_google_read_tools(file_tools, app.state.google_api_client)
    app.state.tool_registry = file_tools
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
