"""Incremental vector indexing for client-scoped knowledge chunks."""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.knowledge import EmbeddingClient
from app.models import KnowledgeChunkEmbeddingRecord
from app.repositories import (
    KnowledgeChunkRepository,
    KnowledgeEmbeddingRepository,
    KnowledgeSourceRepository,
)
from app.services.knowledge import KnowledgeSourceNotFoundError
from logs import log


class KnowledgeEmbeddingIndexError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeEmbeddingIndexResult:
    provider: str
    model: str
    indexed: int
    unchanged: int


class KnowledgeEmbeddingService:
    def __init__(self, session: AsyncSession, client: EmbeddingClient) -> None:
        self._session = session
        self._client = client
        self._sources = KnowledgeSourceRepository(session)
        self._chunks = KnowledgeChunkRepository(session)
        self._embeddings = KnowledgeEmbeddingRepository(session)

    async def index_source(
        self,
        client_id: str,
        source_id: str,
        *,
        batch_size: int = 32,
    ) -> KnowledgeEmbeddingIndexResult:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        if await self._sources.get(client_id, source_id) is None:
            raise KnowledgeSourceNotFoundError("Knowledge source not found")

        chunks = list(await self._chunks.list_for_source(client_id, source_id))
        records = await self._embeddings.list_for_model(
            client_id,
            source_id,
            self._client.provider,
            self._client.model,
        )
        by_chunk = {record.chunk_id: record for record in records}
        stale = [
            chunk
            for chunk in chunks
            if chunk.id not in by_chunk
            or by_chunk[chunk.id].content_hash != chunk.content_hash
        ]
        try:
            for offset in range(0, len(stale), batch_size):
                batch = stale[offset : offset + batch_size]
                vectors = await self._client.embed_documents(
                    [chunk.content for chunk in batch]
                )
                if len(vectors) != len(batch):
                    raise KnowledgeEmbeddingIndexError("Embedding count mismatch")
                for chunk, vector in zip(batch, vectors, strict=True):
                    if len(vector) != self._client.dimensions:
                        raise KnowledgeEmbeddingIndexError("Embedding dimension mismatch")
                    record = by_chunk.get(chunk.id)
                    if record is None:
                        record = KnowledgeChunkEmbeddingRecord(
                            client_id=client_id,
                            source_id=source_id,
                            chunk_id=chunk.id,
                            provider=self._client.provider,
                            model=self._client.model,
                        )
                        self._embeddings.add(record)
                    record.dimensions = self._client.dimensions
                    record.vector = [float(value) for value in vector]
                    record.content_hash = chunk.content_hash
            await self._session.commit()
        except Exception as error:
            await self._session.rollback()
            log.warning(
                "db_mutation_rolled_back table=knowledge_chunk_embeddings "
                "business=knowledge_embedding_index client_id={} source_id={} "
                "error_type={}",
                client_id,
                source_id,
                type(error).__name__,
            )
            raise

        result = KnowledgeEmbeddingIndexResult(
            provider=self._client.provider,
            model=self._client.model,
            indexed=len(stale),
            unchanged=len(chunks) - len(stale),
        )
        log.info(
            "db_mutation_committed table=knowledge_chunk_embeddings "
            "business=knowledge_embedding_index client_id={} source_id={} result={}",
            client_id,
            source_id,
            result,
        )
        return result
