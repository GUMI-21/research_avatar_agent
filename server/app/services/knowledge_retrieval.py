"""Application boundary for client-scoped knowledge retrieval."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import (
    KeywordChunkHit,
    KnowledgeChunkRepository,
    KnowledgeSourceRepository,
)
from app.services.knowledge import KnowledgeSourceNotFoundError
from logs import log


class KnowledgeRetrievalService:
    def __init__(self, session: AsyncSession) -> None:
        self._sources = KnowledgeSourceRepository(session)
        self._chunks = KnowledgeChunkRepository(session)

    async def search_keyword(
        self,
        client_id: str,
        source_id: str,
        query: str,
        *,
        limit: int,
    ) -> list[KeywordChunkHit]:
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
