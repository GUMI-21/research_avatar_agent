"""Replaceable adapters for local knowledge ingestion and retrieval."""

from app.adapters.knowledge.chunking import MarkdownChunk, chunk_markdown
from app.adapters.knowledge.embedding import EmbeddingClient, HashEmbeddingAdapter
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
    "EmbeddingClient",
    "HashEmbeddingAdapter",
    "ParsedMarkdownDocument",
    "ScannedMarkdownFile",
    "chunk_markdown",
    "build_fts_query",
    "parse_markdown",
    "scan_markdown_files",
]
