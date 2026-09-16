"""Native and MCP tool execution boundaries."""

from app.tools.approval import ToolApprovalBroker
from app.tools.filesystem import create_file_tool_registry
from app.tools.mcp import MCPClient, MCPError, MCPTransport
from app.tools.mcp_stdio import StdioMCPTransport
from app.tools.registry import (
    ToolApprovalRequiredError,
    ToolArguments,
    ToolContext,
    ToolNotFoundError,
    ToolRegistry,
    ToolResult,
    ToolRisk,
    ToolSpec,
)

__all__ = [
    "MCPClient",
    "MCPError",
    "MCPTransport",
    "StdioMCPTransport",
    "ToolApprovalBroker",
    "ToolApprovalRequiredError",
    "ToolArguments",
    "ToolContext",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolResult",
    "ToolRisk",
    "ToolSpec",
    "create_file_tool_registry",
]
