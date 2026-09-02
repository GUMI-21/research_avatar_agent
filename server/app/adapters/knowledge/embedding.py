"""Replaceable embedding boundary for knowledge retrieval."""

from collections.abc import Sequence
from hashlib import sha256
from math import sqrt
from typing import Protocol


class EmbeddingClient(Protocol):
    """Encode queries and documents without exposing a model SDK."""

    provider: str
    model: str
    dimensions: int

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class HashEmbeddingAdapter:
    """Deterministic plumbing adapter; it does not provide semantic similarity."""

    provider = "local"
    model = "hash-test-v1"

    def __init__(self, dimensions: int = 8) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._encode(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._encode(text)

    def _encode(self, text: str) -> list[float]:
        raw = bytearray()
        block = 0
        while len(raw) < self.dimensions:
            raw.extend(sha256(f"{block}:{text}".encode()).digest())
            block += 1
        values = [(byte / 127.5) - 1.0 for byte in raw[: self.dimensions]]
        norm = sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]
