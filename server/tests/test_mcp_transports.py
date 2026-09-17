"""Tests for the official SDK-backed stdio MCP transport."""

import unittest
from unittest.mock import patch

from app.tools import MCPError, StdioMCPTransport, StreamableHttpMCPTransport


class FakeResult:
    def __init__(self, value: dict[str, object]) -> None:
        self.value = value

    def model_dump(self, **_options: object) -> dict[str, object]:
        return self.value


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args: object) -> None:
        self.closed = True

    async def list_tools(self) -> FakeResult:
        self.calls.append(("list", None))
        return FakeResult({"tools": [{"name": "search"}]})

    async def call_tool(self, name: str, arguments: dict[str, object]) -> FakeResult:
        self.calls.append((name, arguments))
        return FakeResult({"content": [{"type": "text", "text": "ok"}]})


class StdioMCPTransportTest(unittest.IsolatedAsyncioTestCase):
    async def test_requires_connection_and_maps_supported_methods(self) -> None:
        fake = FakeClient()
        transport = StdioMCPTransport("fake-server", ["--stdio"])
        with self.assertRaisesRegex(MCPError, "not connected"):
            await transport.request("tools/list")

        with patch("app.tools.mcp_sdk.Client", return_value=fake) as factory:
            async with transport:
                listed = await transport.request("tools/list")
                called = await transport.request("tools/call", {
                    "name": "search", "arguments": {"query": "agents"},
                })

        self.assertEqual(listed["tools"], [{"name": "search"}])
        self.assertEqual(called["content"], [{"type": "text", "text": "ok"}])
        self.assertEqual(fake.calls[-1], ("search", {"query": "agents"}))
        self.assertTrue(fake.closed)
        parameters = factory.call_args.args[0]
        self.assertEqual(parameters.command, "fake-server")
        self.assertEqual(parameters.args, ["--stdio"])

    async def test_streamable_http_uses_url_client(self) -> None:
        fake = FakeClient()
        with patch("app.tools.mcp_sdk.Client", return_value=fake) as factory:
            async with StreamableHttpMCPTransport(
                "http://127.0.0.1:8931/mcp"
            ) as transport:
                listed = await transport.request("tools/list")

        self.assertEqual(listed["tools"], [{"name": "search"}])
        self.assertEqual(factory.call_args.args[0], "http://127.0.0.1:8931/mcp")
        self.assertTrue(fake.closed)

    async def test_rejects_unknown_method_and_invalid_call(self) -> None:
        fake = FakeClient()
        with patch("app.tools.mcp_sdk.Client", return_value=fake):
            async with StdioMCPTransport("fake-server") as transport:
                with self.assertRaisesRegex(MCPError, "Unsupported"):
                    await transport.request("resources/list")
                with self.assertRaisesRegex(MCPError, "parameters"):
                    await transport.request("tools/call", {"name": 42})


if __name__ == "__main__":
    unittest.main()