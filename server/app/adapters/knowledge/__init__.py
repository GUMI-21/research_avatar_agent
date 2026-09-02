"""Filesystem adapters for local Markdown knowledge sources."""

from app.adapters.knowledge.chunking import MarkdownChunk, chunk_markdown
from app.adapters.knowledge.filesystem import ScannedMarkdownFile, scan_markdown_files
from app.adapters.knowledge.markdown import (
    MarkdownParseError,
    ParsedMarkdownDocument,
    parse_markdown,
)
from app.adapters.knowledge.search import build_fts_query

__all__ = [
    "MarkdownParseError",
    "MarkdownChunk",
    "ParsedMarkdownDocument",
    "ScannedMarkdownFile",
    "chunk_markdown",
    "build_fts_query",
    "parse_markdown",
    "scan_markdown_files",
]
