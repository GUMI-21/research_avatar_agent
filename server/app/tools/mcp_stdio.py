"""Official MCP SDK transport for local stdio servers."""

from collections.abc import Mapping, Sequence
from contextlib import AsyncExitStack
from pathlib import Path
from types import TracebackType
from typing import cast

from mcp import Client, StdioServerParameters

from app.tools.mcp import MCPError


class StdioMCPTransport:
    def __init__(
        self,
        command: str,
        args: Sequence[str] = (),
        *,
        cwd: Path | None = None,
        timeout_seconds: float = 30,
    ) -> None:
        self._parameters = StdioServerParameters(
            command=command, args=list(args), cwd=cwd,
        )
        self._timeout_seconds = timeout_seconds
        self._stack = AsyncExitStack()
        self._client: Client | None = None

    async def __aenter__(self) -> "StdioMCPTransport":
        try:
            self._client = await self._stack.enter_async_context(Client(
                self._parameters, read_timeout_seconds=self._timeout_seconds,
            ))
        except BaseException:
            await self._stack.aclose()
            raise
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        await self._stack.aclose()
        self._client = None

    async def request(
        self, method: str, params: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]:
        if self._client is None:
            raise MCPError("MCP stdio transport is not connected")
        if method == "tools/list":
            result = await self._client.list_tools()
        elif method == "tools/call":
            values = dict(params or {})
            name = values.get("name")
            arguments = values.get("arguments", {})
            if not isinstance(name, str) or not isinstance(arguments, dict):
                raise MCPError("MCP tools/call parameters are invalid")
            result = await self._client.call_tool(name, arguments)
        else:
            raise MCPError(f"Unsupported MCP method '{method}'")
        return cast(Mapping[str, object], result.model_dump(
            mode="json", by_alias=True, exclude_none=True,
        ))