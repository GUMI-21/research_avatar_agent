"""Probe one configured MCP server and print its discovered tool names."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.settings import load_settings
from app.tools import (
    MCPClient,
    StdioMCPTransport,
    StreamableHttpMCPTransport,
    ToolContext,
    ToolRegistry,
)


async def _inspect(
    client: MCPClient, server_name: str, navigate_url: str | None,
) -> tuple[str, ...]:
    registry = ToolRegistry(timeout_seconds=60)
    names = await client.register_tools(registry)
    if navigate_url is not None:
        tool_name = f"mcp_{server_name}_browser_navigate"
        result = await registry.execute(
            tool_name,
            ToolContext("mcp-check", "mcp-check"),
            {"url": navigate_url},
            approved=True,
        )
        print(f"Navigation succeeded: {len(result.content)} result characters")
    return names


async def probe(
    environment: str, server_name: str, navigate_url: str | None = None,
) -> tuple[str, ...]:
    settings = load_settings(environment)
    for config in settings.mcp.stdio_servers:
        if config.name != server_name:
            continue
        async with StdioMCPTransport(
            config.command,
            config.args,
            cwd=config.cwd,
            timeout_seconds=config.timeout_seconds,
        ) as transport:
            client = MCPClient(
                config.name,
                transport,
                config.allowed_domains,
                config.blocked_tools,
            )
            return await _inspect(client, config.name, navigate_url)

    for config in settings.mcp.http_servers:
        if config.name != server_name:
            continue
        async with StreamableHttpMCPTransport(
            str(config.url), timeout_seconds=config.timeout_seconds,
        ) as transport:
            client = MCPClient(
                config.name,
                transport,
                config.allowed_domains,
                config.blocked_tools,
            )
            return await _inspect(client, config.name, navigate_url)

    raise ValueError(
        f"MCP server '{server_name}' is not configured for '{environment}'"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default="debug")
    parser.add_argument("--server", required=True)
    parser.add_argument("--navigate")
    arguments = parser.parse_args()
    names = asyncio.run(probe(arguments.env, arguments.server, arguments.navigate))
    print(f"Connected to {arguments.server}: {len(names)} tools")
    for name in names:
        print(f"- {name}")


if __name__ == "__main__":
    main()