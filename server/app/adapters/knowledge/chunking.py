"""Split Markdown by heading context while preserving source line locations."""

import re
from dataclasses import dataclass
from hashlib import sha256


HEADING_LINE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FENCE_LINE = re.compile(r"^\s*(?:```|~~~)")
DATA_IMAGE_LINE = re.compile(r"^\s*!\[[^\]]*\]\(\s*data:image/", re.IGNORECASE)


@dataclass(frozen=True)
class MarkdownChunk:
    chunk_index: int
    heading_path: tuple[str, ...]
    content: str
    start_line: int
    end_line: int
    content_hash: str


def _body_start(lines: list[str]) -> int:
    if not lines or lines[0].strip() != "---":
        return 0
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return index + 1
    raise ValueError("YAML frontmatter is missing its closing delimiter")

# markdown切片
def chunk_markdown(raw_text: str, *, max_chars: int = 1200) -> list[MarkdownChunk]:
    if max_chars < 1:
        raise ValueError("max_chars must be positive")
    lines = raw_text.splitlines()
    chunks: list[MarkdownChunk] = []
    heading_path: list[str] = []
    buffered: list[tuple[int, str]] = []
    buffered_chars = 0
    in_fence = False

    def flush() -> None:
        nonlocal buffered, buffered_chars
        while buffered and not buffered[-1][1].strip():
            buffered.pop()
        if buffered:
            content = "\n".join(line for _, line in buffered)
            chunks.append(
                MarkdownChunk(
                    chunk_index=len(chunks),
                    heading_path=tuple(heading_path),
                    content=content,
                    start_line=buffered[0][0],
                    end_line=buffered[-1][0],
                    content_hash=sha256(content.encode()).hexdigest(),
                )
            )
        buffered = []
        buffered_chars = 0

    start = _body_start(lines)
    for line_number, line in enumerate(lines[start:], start=start + 1):
        heading = None if in_fence else HEADING_LINE.match(line)
        if heading is not None:
            flush()
            level = len(heading.group(1))
            heading_path = heading_path[: level - 1]
            heading_path.append(heading.group(2).strip())
            continue
        if DATA_IMAGE_LINE.match(line):
            flush()
            continue
        if not buffered and not line.strip():
            continue
        if len(line) > max_chars:
            flush()
            for offset in range(0, len(line), max_chars):
                buffered.append((line_number, line[offset : offset + max_chars]))
                buffered_chars = len(buffered[0][1])
                flush()
            continue
        if buffered and buffered_chars + len(line) + 1 > max_chars:
            flush()
        buffered.append((line_number, line))
        buffered_chars += len(line) + 1
        if FENCE_LINE.match(line):
            in_fence = not in_fence
    flush()
    return chunks
