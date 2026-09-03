"""Application boundary for client-scoped knowledge retrieval."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.knowledge import EmbeddingClient
from app.repositories import (
    KnowledgeChunkHit,
    KnowledgeChunkRepository,
    KnowledgeSourceRepository,
)
from app.services.knowledge import KnowledgeSourceNotFoundError
from logs import log


class KnowledgeRetrievalService:
    def __init__(
        self,
        session: AsyncSession,
        embedding_client: EmbeddingClient | None = None,
    ) -> None:
        self._sources = KnowledgeSourceRepository(session)
        self._chunks = KnowledgeChunkRepository(session)
        self._embedding_client = embedding_client

    async def search_keyword(
        self,
        client_id: str,
        source_id: str,
        query: str,
        *,
        limit: int,
    ) -> list[KnowledgeChunkHit]:
        source = await self._sources.get(client_id, source_id)
        if source is None:
            raise KnowledgeSourceNotFoundError("Knowledge source not found")
        hits = await self._chunks.search_keyword(
            client_id,
            query,
            source_id=source_id,
            limit=limit,
        )
        log.info(
            "knowledge_retrieval_completed strategy=keyword client_id={} "
            "source_id={} query_length={} hit_count={}",
            client_id,
            source_id,
            len(query),
            len(hits),
        )
        return hits

    # 根据向量相似度搜索
    async def search_vector(
        self,
        client_id: str,
        source_id: str,
        query: str,
        *,
        limit: int,
    ) -> list[KnowledgeChunkHit]:
        if await self._sources.get(client_id, source_id) is None:
            raise KnowledgeSourceNotFoundError("Knowledge source not found")
        if self._embedding_client is None:
            raise RuntimeError("Embedding client is required for vector search")
        query_vector = await self._embedding_client.embed_query(query)
        hits = await self._chunks.search_vector(
            client_id,
            source_id,
            self._embedding_client.provider,
            self._embedding_client.model,
            query_vector,
            limit=limit,
        )
        log.info(
            "knowledge_retrieval_completed strategy=vector client_id={} "
            "source_id={} query_length={} hit_count={}",
            client_id,
            source_id,
            len(query),
            len(hits),
        )
        return hits
