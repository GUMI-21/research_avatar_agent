"""Tests for guarded provider-neutral tool execution."""

import asyncio
import unittest

from pydantic import Field, ValidationError

from app.tools import (
    ToolApprovalRequiredError,
    ToolArguments,
    ToolContext,
    ToolRegistry,
    ToolResult,
    ToolRisk,
    ToolSpec,
)


class ReadArguments(ToolArguments):
    path: str = Field(min_length=1)


async def read_handler(
    context: ToolContext, arguments: ToolArguments,
) -> ToolResult:
    assert isinstance(arguments, ReadArguments)
    return ToolResult(
        content=f"{context.client_id}:{arguments.path}",
        metadata={"path": arguments.path},
    )


class ToolRegistryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.registry = ToolRegistry()
        self.registry.register(ToolSpec(
            name="read_server_file",
            description="Read one server file.",
            arguments=ReadArguments,
            risk=ToolRisk.READ_ONLY,
            handler=read_handler,
        ))
        self.context = ToolContext("client-a", "agent-a", "server")

    async def test_exposes_schema_and_executes_validated_read(self) -> None:
        definition = self.registry.definitions({"read_server_file"})[0]
        result = await self.registry.execute(
            "read_server_file", self.context, {"path": "README.md"},
        )

        self.assertEqual(definition.name, "read_server_file")
        self.assertIn("path", definition.input_schema["required"])
        self.assertEqual(result.content, "client-a:README.md")

    async def test_rejects_unknown_arguments_and_tools(self) -> None:
        with self.assertRaises(ValidationError):
            await self.registry.execute(
                "read_server_file", self.context,
                {"path": "README.md", "secret": "unexpected"},
            )
        with self.assertRaises(LookupError):
            await self.registry.execute("missing", self.context, {})

    async def test_applies_timeout(self) -> None:
        async def slow_handler(
            context: ToolContext, arguments: ToolArguments,
        ) -> ToolResult:
            del context, arguments
            await asyncio.sleep(0.02)
            return ToolResult(content="late")

        registry = ToolRegistry(timeout_seconds=0.001)
        registry.register(ToolSpec(
            name="slow_read", description="Slow read.",
            arguments=ReadArguments, risk=ToolRisk.READ_ONLY,
            handler=slow_handler,
        ))
        with self.assertRaises(TimeoutError):
            await registry.execute(
                "slow_read", self.context, {"path": "README.md"},
            )

    async def test_requires_approval_for_side_effects(self) -> None:
        self.registry.register(ToolSpec(
            name="write_server_file",
            description="Write one server file.",
            arguments=ReadArguments,
            risk=ToolRisk.LOCAL_WRITE,
            handler=read_handler,
        ))

        with self.assertRaises(ToolApprovalRequiredError):
            await self.registry.execute(
                "write_server_file", self.context, {"path": "README.md"},
            )
        result = await self.registry.execute(
            "write_server_file", self.context, {"path": "README.md"},
            approved=True,
        )
        self.assertEqual(result.metadata["path"], "README.md")


if __name__ == "__main__":
    unittest.main()