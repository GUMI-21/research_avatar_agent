"""Provider-neutral tool contracts and guarded execution registry."""

import asyncio
import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.adapters.llm import LLMToolDefinition

_TOOL_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MAX_RESULT_CHARS = 20_000


class ToolRisk(StrEnum):
    READ_ONLY = "read_only"
    LOCAL_WRITE = "local_write"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass(frozen=True)
class ToolContext:
    client_id: str
    agent_id: str
    workspace_path: str | None = None


@dataclass(frozen=True)
class ToolResult:
    content: str
    metadata: Mapping[str, object] = field(default_factory=dict)


ToolHandler = Callable[[ToolContext, ToolArguments], Awaitable[ToolResult]]
ToolValidator = Callable[[Mapping[str, object]], None]


# Tool Specification 工具规格定义
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    arguments: type[ToolArguments]
    risk: ToolRisk
    handler: ToolHandler
    input_schema: Mapping[str, object] | None = None
    validator: ToolValidator | None = None

    def llm_definition(self) -> LLMToolDefinition:
        return LLMToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=(
                self.input_schema
                if self.input_schema is not None
                else self.arguments.model_json_schema()
            ),
        )


class ToolNotFoundError(LookupError):
    pass


class ToolApprovalRequiredError(PermissionError):
    def __init__(self, tool: ToolSpec) -> None:
        super().__init__(f"Tool '{tool.name}' requires approval")
        self.tool = tool


# tool call
class ToolRegistry:
    """Expose registered schemas and execute only approved side effects."""

    def __init__(self, timeout_seconds: float = 30) -> None:
        if timeout_seconds <= 0:
            raise ValueError("Tool timeout must be positive")
        self._timeout_seconds = timeout_seconds
        self._tools: dict[str, ToolSpec] = {}

    # register tool
    def register(self, tool: ToolSpec) -> None:
        if not _TOOL_NAME.fullmatch(tool.name):
            raise ValueError("Tool name must use lowercase snake_case")
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def definitions(
        self, allowed_names: set[str] | None = None,
    ) -> tuple[LLMToolDefinition, ...]:
        return tuple(
            tool.llm_definition()
            for name, tool in self._tools.items()
            if allowed_names is None or name in allowed_names
        )

    async def execute(
        self,
        name: str,
        context: ToolContext,
        arguments: Mapping[str, object],
        *,
        approved: bool = False,
    ) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolNotFoundError(name)
        if tool.risk is not ToolRisk.READ_ONLY and not approved:
            raise ToolApprovalRequiredError(tool)
        raw_arguments = dict(arguments)
        if tool.validator is not None:
            tool.validator(raw_arguments)
        validated = tool.arguments.model_validate(raw_arguments)
        async with asyncio.timeout(self._timeout_seconds):
            result = await tool.handler(context, validated)
        if len(result.content) <= _MAX_RESULT_CHARS:
            return result
        return ToolResult(
            content=result.content[:_MAX_RESULT_CHARS],
            metadata={**result.metadata, "truncated": True},
        )
