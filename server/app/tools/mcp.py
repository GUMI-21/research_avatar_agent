"""Map MCP tool discovery and calls into the guarded Tool Registry."""

import json
import re
from collections.abc import Mapping
from typing import Protocol, cast
from urllib.parse import urlsplit

from jsonschema.validators import validator_for
from pydantic import ConfigDict

from app.tools.registry import (
    ToolArguments, ToolContext, ToolRegistry, ToolResult, ToolRisk, ToolSpec,
    ToolValidator,
)


class MCPError(RuntimeError):
    pass


class MCPTransport(Protocol):
    async def request(
        self, method: str, params: Mapping[str, object] | None = None,
    ) -> Mapping[str, object]: ...


class MCPArguments(ToolArguments):
    model_config = ConfigDict(extra="allow")


def _tool_name(server: str, remote_name: str) -> str:
    normalized = re.sub(r"[^a-z0-9_]+", "_", f"mcp_{server}_{remote_name}".lower())
    return normalized.strip("_")[:64]


class MCPClient:
    def __init__(
        self,
        server_name: str,
        transport: MCPTransport,
        allowed_domains: tuple[str, ...] = (),
        blocked_tools: tuple[str, ...] = (),
    ) -> None:
        self._server_name = server_name
        self._transport = transport
        self._allowed_domains = tuple(
            domain.lower().rstrip(".") for domain in allowed_domains
        )
        self._blocked_tools = frozenset(blocked_tools)

    def _validate_urls(self, value: object, key: str = "") -> None:
        if not self._allowed_domains:
            return
        if isinstance(value, Mapping):
            for child_key, child_value in value.items():
                self._validate_urls(child_value, str(child_key).lower())
            return
        if isinstance(value, list):
            for child_value in value:
                self._validate_urls(child_value, key)
            return
        if not isinstance(value, str) or not (
            key == "url" or key.endswith("_url")
        ):
            return
        parsed = urlsplit(value)
        hostname = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or not hostname:
            raise MCPError("MCP browser URL must use HTTP or HTTPS")
        if not any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in self._allowed_domains
        ):
            raise MCPError(f"MCP browser domain '{hostname}' is not allowed")

    async def register_tools(
        self, registry: ToolRegistry, risk: ToolRisk = ToolRisk.EXTERNAL_READ,
    ) -> tuple[str, ...]:
        response = await self._transport.request("tools/list")
        tools = response.get("tools")
        if not isinstance(tools, list):
            raise MCPError("MCP tools/list returned an invalid result")
        registered: list[str] = []
        for item in tools:
            if not isinstance(item, Mapping):
                raise MCPError("MCP tool definition is invalid")
            remote_name = item.get("name")
            schema = item.get("inputSchema", {"type": "object"})
            if not isinstance(remote_name, str) or not isinstance(schema, Mapping):
                raise MCPError("MCP tool name or input schema is invalid")
            if remote_name in self._blocked_tools:
                continue
            schema = dict(schema)
            validator_type = validator_for(schema)
            validator_type.check_schema(schema)
            validator = validator_type(schema)
            argument_validator = cast(ToolValidator, validator.validate)
            local_name = _tool_name(self._server_name, remote_name)
            registry.register(ToolSpec(
                name=local_name,
                description=str(item.get("description") or remote_name),
                arguments=MCPArguments,
                risk=risk,
                handler=self._handler(remote_name),
                input_schema=schema,
                validator=argument_validator,
            ))
            registered.append(local_name)
        return tuple(registered)

    def _handler(self, remote_name: str):
        async def call(
            _context: ToolContext, arguments: ToolArguments,
        ) -> ToolResult:
            values = arguments.model_dump(exclude_unset=True)
            self._validate_urls(values)
            response = await self._transport.request("tools/call", {
                "name": remote_name,
                "arguments": values,
            })
            if response.get("isError") is True:
                raise MCPError(f"MCP tool '{remote_name}' failed")
            content = response.get("content", [])
            if not isinstance(content, list):
                raise MCPError("MCP tools/call returned invalid content")
            text = "\n".join(
                str(part["text"]) for part in content
                if isinstance(part, Mapping) and part.get("type") == "text"
            )
            if not text and response.get("structuredContent") is not None:
                text = json.dumps(response["structuredContent"], ensure_ascii=False)
            return ToolResult(text or "(empty)", {
                "mcp_server": self._server_name, "mcp_tool": remote_name,
            })
        return call