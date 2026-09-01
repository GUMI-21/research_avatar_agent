"""Deterministic, root-contained discovery of local Markdown files."""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path


IGNORED_DIRECTORIES = {".git", ".obsidian", ".trash", "node_modules"}
MARKDOWN_SUFFIXES = {".md", ".markdown"}


@dataclass(frozen=True)
class ScannedMarkdownFile:
    path: Path
    relative_path: str
    content_hash: str
    source_modified_at: datetime
    size_bytes: int


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source_file:
        for block in iter(lambda: source_file.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scan_markdown_files(root_path: Path) -> list[ScannedMarkdownFile]:
    root = root_path.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)

    scanned: list[ScannedMarkdownFile] = []
    for directory, child_directories, file_names in os.walk(
        root,
        followlinks=False,
    ):
        child_directories[:] = sorted(
            name
            for name in child_directories
            if name not in IGNORED_DIRECTORIES and not name.startswith(".")
        )
        for file_name in sorted(file_names):
            if file_name.startswith("."):
                continue
            candidate = Path(directory) / file_name
            if candidate.suffix.lower() not in MARKDOWN_SUFFIXES:
                continue
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if not resolved.is_relative_to(root) or not resolved.is_file():
                continue
            file_stat = resolved.stat()
            scanned.append(
                ScannedMarkdownFile(
                    path=resolved,
                    relative_path=candidate.relative_to(root).as_posix(),
                    content_hash=_hash_file(resolved),
                    source_modified_at=datetime.fromtimestamp(
                        file_stat.st_mtime,
                        timezone.utc,
                    ),
                    size_bytes=file_stat.st_size,
                )
            )
    return sorted(scanned, key=lambda item: item.relative_path)
