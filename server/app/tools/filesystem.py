"""File tools that inherit the Server process filesystem permissions."""

import asyncio
from itertools import islice
from pathlib import Path

from pydantic import Field

from app.tools.registry import (
    ToolArguments,
    ToolContext,
    ToolRegistry,
    ToolResult,
    ToolRisk,
    ToolSpec,
)


class ListFilesArguments(ToolArguments):
    path: str = "."
    max_entries: int = Field(default=200, ge=1, le=500)


class ReadTextFileArguments(ToolArguments):
    path: str = Field(min_length=1)
    max_chars: int = Field(default=12_000, ge=1, le=20_000)


class WriteMarkdownArguments(ToolArguments):
    path: str = Field(min_length=1)
    content: str = Field(max_length=100_000)


def _resolve_path(base: Path, requested: str) -> Path:
    candidate = Path(requested).expanduser()
    return (candidate if candidate.is_absolute() else base / candidate).resolve()


def create_file_tool_registry(default_directory: Path | None = None) -> ToolRegistry:
    """Create file tools governed by the Server operating-system identity."""
    base = (default_directory or Path.cwd()).resolve()
    registry = ToolRegistry()

    async def list_files(
        _context: ToolContext, arguments: ToolArguments
    ) -> ToolResult:
        assert isinstance(arguments, ListFilesArguments)
        directory = _resolve_path(base, arguments.path)
        if not directory.is_dir():
            raise ValueError("Path is not a directory")
        entries = await asyncio.to_thread(
            lambda: list(islice(directory.iterdir(), arguments.max_entries + 1))
        )
        visible = entries[: arguments.max_entries]
        content = "\n".join(
            f"{item.as_posix()}{'/' if item.is_dir() else ''}" for item in visible
        )
        return ToolResult(
            content or "(empty)", {"truncated": len(entries) > len(visible)}
        )

    async def read_text_file(
        _context: ToolContext, arguments: ToolArguments
    ) -> ToolResult:
        assert isinstance(arguments, ReadTextFileArguments)
        path = _resolve_path(base, arguments.path)
        if not path.is_file():
            raise ValueError("Path is not a file")

        def read_prefix() -> str:
            with path.open(encoding="utf-8") as source:
                return source.read(arguments.max_chars + 1)

        text = await asyncio.to_thread(read_prefix)
        return ToolResult(
            text[: arguments.max_chars],
            {"truncated": len(text) > arguments.max_chars},
        )

    async def write_markdown(
        _context: ToolContext, arguments: ToolArguments
    ) -> ToolResult:
        assert isinstance(arguments, WriteMarkdownArguments)
        path = _resolve_path(base, arguments.path)
        if path.suffix.lower() != ".md" or not path.parent.is_dir():
            raise ValueError("Markdown path or parent directory is invalid")
        await asyncio.to_thread(path.write_text, arguments.content, encoding="utf-8")
        return ToolResult("Markdown file written", {"path": str(path)})

    registry.register(ToolSpec(
        "list_files", "List a directory accessible to the Server process.",
        ListFilesArguments, ToolRisk.READ_ONLY, list_files,
    ))
    registry.register(ToolSpec(
        "read_text_file", "Read a UTF-8 file accessible to the Server process.",
        ReadTextFileArguments, ToolRisk.READ_ONLY, read_text_file,
    ))
    registry.register(ToolSpec(
        "write_markdown", "Create or replace a Markdown file.",
        WriteMarkdownArguments, ToolRisk.LOCAL_WRITE, write_markdown,
    ))
    return registry
