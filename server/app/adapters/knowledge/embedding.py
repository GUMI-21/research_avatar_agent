"""Replaceable embedding boundary for knowledge retrieval."""

import asyncio
import warnings
from collections.abc import Iterable, Sequence
from hashlib import sha256
from math import sqrt
from pathlib import Path
from typing import Protocol

from fastembed import TextEmbedding

DEFAULT_FASTEMBED_MODEL = (
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


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

# embedding model
class FastEmbedAdapter:
    """Run a multilingual ONNX embedding model without blocking the event loop."""

    provider = "fastembed"

    def __init__(
        self,
        model: str = DEFAULT_FASTEMBED_MODEL,
        dimensions: int = 384,
        cache_dir: Path | None = None,
    ) -> None:
        if dimensions < 1:
            raise ValueError("dimensions must be positive")
        self.model = model
        self.dimensions = dimensions
        # FastEmbed warns about its intentional switch to the model's mean pooling.
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message=r"The model .* now uses mean pooling instead of CLS embedding.*",
            )
            self._engine = TextEmbedding(
                model_name=model,
                cache_dir=str(cache_dir) if cache_dir is not None else None,
                lazy_load=True,
            )

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        documents = list(texts)
        vectors = await asyncio.to_thread(
            lambda: list(self._engine.passage_embed(documents))
        )
        return [self._normalize(vector) for vector in vectors]

    async def embed_query(self, text: str) -> list[float]:
        vectors = await asyncio.to_thread(lambda: list(self._engine.query_embed(text)))
        return self._normalize(vectors[0])

    @staticmethod
    def _normalize(vector: Iterable[float]) -> list[float]:
        values = [float(value) for value in vector]
        norm = sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]
