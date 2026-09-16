"""Tests for MCP discovery and guarded tool execution."""

import unittest
from collections.abc import Mapping

from jsonschema import ValidationError

from app.tools import MCPClient, MCPError, ToolApprovalRequiredError, ToolContext, ToolRegistry


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Mapping[str, object] | None]] = []
        self.fail = False
        self.schema: Mapping[str, object] = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        }

    async def request(self, method: str, params=None):
        self.calls.append((method, params))
        if method == "tools/list":
            return {"tools": [{
                "name": "search-web",
                "description": "Search the web.",
                "inputSchema": self.schema,
            }]}
        if self.fail:
            return {"isError": True, "content": [{"type": "text", "text": "secret"}]}
        return {"content": [{"type": "text", "text": "result"}]}


class MCPClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.transport = FakeTransport()
        self.registry = ToolRegistry()
        self.names = await MCPClient("browser", self.transport).register_tools(self.registry)
        self.context = ToolContext("client-a", "agent-a")

    async def test_discovers_schema_and_executes_through_registry(self) -> None:
        self.assertEqual(self.names, ("mcp_browser_search_web",))
        definition = self.registry.definitions()[0]
        self.assertEqual(definition.input_schema["required"], ["query"])
        with self.assertRaises(ToolApprovalRequiredError):
            await self.registry.execute(definition.name, self.context, {"query": "agents"})
        result = await self.registry.execute(
            definition.name, self.context, {"query": "agents"}, approved=True,
        )
        self.assertEqual(result.content, "result")
        self.assertEqual(self.transport.calls[-1][1], {
            "name": "search-web", "arguments": {"query": "agents"},
        })

    async def test_validates_arguments_before_remote_call(self) -> None:
        with self.assertRaises(ValidationError):
            await self.registry.execute(
                self.names[0], self.context, {"unexpected": True}, approved=True,
            )
        self.assertEqual(len(self.transport.calls), 1)

    async def test_normalizes_remote_tool_error_without_content(self) -> None:
        self.transport.fail = True
        with self.assertRaisesRegex(MCPError, "search-web"):
            await self.registry.execute(
                self.names[0], self.context, {"query": "agents"}, approved=True,
            )

    async def test_browser_url_policy_allows_domains_and_subdomains(self) -> None:
        self.transport.schema = {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
            "additionalProperties": False,
        }
        registry = ToolRegistry()
        names = await MCPClient(
            "browser", self.transport, ("example.com",),
        ).register_tools(registry)
        await registry.execute(
            names[0], self.context, {"url": "https://docs.example.com/agents"},
            approved=True,
        )
        with self.assertRaisesRegex(MCPError, "not allowed"):
            await registry.execute(
                names[0], self.context, {"url": "http://127.0.0.1/admin"},
                approved=True,
            )


if __name__ == "__main__":
    unittest.main()
