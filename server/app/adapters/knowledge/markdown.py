"""Parse Markdown metadata and Obsidian relationships without indexing it."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


OBSIDIAN_LINK = re.compile(r"(!?)\[\[([^\]\n]+)\]\]")
MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*(?:<([^>]+)>|([^\s)]+))")
HEADING = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
IMAGE_SUFFIXES = {
    ".avif",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".svg",
    ".webp",
}


class MarkdownParseError(ValueError):
    """Raised when a document contains invalid frontmatter."""


@dataclass(frozen=True)
class ParsedMarkdownDocument:
    title: str
    content: str
    frontmatter: dict[str, object]
    note_links: tuple[str, ...]
    asset_links: tuple[str, ...]


def _split_frontmatter(raw_text: str) -> tuple[dict[str, object], str]:
    lines = raw_text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, raw_text

    closing_index = next(
        (index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"),
        None,
    )
    if closing_index is None:
        raise MarkdownParseError("YAML frontmatter is missing its closing delimiter")
    try:
        loaded = yaml.safe_load("".join(lines[1:closing_index])) or {}
    except yaml.YAMLError as error:
        raise MarkdownParseError("Invalid YAML frontmatter") from error
    if not isinstance(loaded, dict):
        raise MarkdownParseError("YAML frontmatter must be a mapping")
    return {str(key): value for key, value in loaded.items()}, "".join(lines[closing_index + 1 :])


def _unique(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def parse_markdown(relative_path: str, raw_text: str) -> ParsedMarkdownDocument:
    frontmatter, content = _split_frontmatter(raw_text)
    note_links: list[str] = []
    asset_links: list[str] = []
    for match in OBSIDIAN_LINK.finditer(content):
        embedded, raw_target = match.groups()
        target = raw_target.split("|", maxsplit=1)[0].strip()
        path_target = target.split("#", maxsplit=1)[0]
        if embedded and Path(path_target).suffix.lower() in IMAGE_SUFFIXES:
            asset_links.append(path_target)
        else:
            note_links.append(target)

    asset_links.extend(
        (angle_target or plain_target).strip()
        for angle_target, plain_target in MARKDOWN_IMAGE.findall(content)
    )
    metadata_title = frontmatter.get("title")
    heading = HEADING.search(content)
    title = (
        metadata_title.strip()
        if isinstance(metadata_title, str) and metadata_title.strip()
        else heading.group(1).strip()
        if heading
        else Path(relative_path).stem
    )
    return ParsedMarkdownDocument(
        title=title,
        content=content,
        frontmatter=frontmatter,
        note_links=_unique(note_links),
        asset_links=_unique(asset_links),
    )
