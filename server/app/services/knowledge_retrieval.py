"""Application boundary for client-scoped knowledge retrieval."""

from collections.abc import Sequence
from dataclasses import replace

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

    # 混合检索，关键词+向量
    async def search_hybrid(
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
            raise RuntimeError("Embedding client is required for hybrid search")
        candidate_limit = min(limit * 3, 60)
        keyword_hits = await self._chunks.search_keyword(
            client_id,
            query,
            source_id=source_id,
            limit=candidate_limit,
        )
        query_vector = await self._embedding_client.embed_query(query)
        vector_hits = await self._chunks.search_vector(
            client_id,
            source_id,
            self._embedding_client.provider,
            self._embedding_client.model,
            query_vector,
            limit=candidate_limit,
        )
        hits = self._reciprocal_rank_fusion(
            (keyword_hits, vector_hits),
            limit=limit,
        )
        log.info(
            "knowledge_retrieval_completed strategy=hybrid client_id={} "
            "source_id={} keyword_count={} vector_count={} hit_count={}",
            client_id,
            source_id,
            len(keyword_hits),
            len(vector_hits),
            len(hits),
        )
        return hits

    @staticmethod
    def _reciprocal_rank_fusion(
        rankings: Sequence[Sequence[KnowledgeChunkHit]],
        *,
        limit: int,
        rank_constant: int = 60,
    ) -> list[KnowledgeChunkHit]:
        scores: dict[str, float] = {}
        hits_by_id: dict[str, KnowledgeChunkHit] = {}
        for ranking in rankings:
            for rank, hit in enumerate(ranking, start=1):
                hits_by_id.setdefault(hit.chunk_id, hit)
                scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1 / (
                    rank_constant + rank
                )
        ordered_ids = sorted(
            scores,
            key=lambda chunk_id: (-scores[chunk_id], chunk_id),
        )
        return [
            replace(hits_by_id[chunk_id], score=scores[chunk_id])
            for chunk_id in ordered_ids[:limit]
        ]
