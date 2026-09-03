"""Client-scoped persistence for local knowledge sources."""

import json
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    KnowledgeChunkEmbeddingRecord,
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
)
from app.adapters.knowledge import build_fts_query


@dataclass(frozen=True)
class KeywordChunkHit:
    chunk_id: str
    document_id: str
    title: str
    relative_path: str
    heading_path: tuple[str, ...]
    content: str
    start_line: int
    end_line: int
    score: float


class KnowledgeSourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        client_id: str,
        *,
        name: str,
        root_path: str,
        source_type: str,
    ) -> KnowledgeSourceRecord:
        source = KnowledgeSourceRecord(
            client_id=client_id,
            name=name,
            root_path=root_path,
            source_type=source_type,
        )
        self._session.add(source)
        await self._session.flush()
        return source

    async def list_sources(
        self,
        client_id: str,
    ) -> Sequence[KnowledgeSourceRecord]:
        statement = (
            select(KnowledgeSourceRecord)
            .where(KnowledgeSourceRecord.client_id == client_id)
            .order_by(KnowledgeSourceRecord.created_at.desc())
        )
        return (await self._session.execute(statement)).scalars().all()

    async def get(
        self,
        client_id: str,
        source_id: str,
    ) -> KnowledgeSourceRecord | None:
        statement = select(KnowledgeSourceRecord).where(
            KnowledgeSourceRecord.client_id == client_id,
            KnowledgeSourceRecord.id == source_id,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def get_by_root(
        self,
        client_id: str,
        root_path: str,
    ) -> KnowledgeSourceRecord | None:
        statement = select(KnowledgeSourceRecord).where(
            KnowledgeSourceRecord.client_id == client_id,
            KnowledgeSourceRecord.root_path == root_path,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()


class KnowledgeDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_source(
        self,
        client_id: str,
        source_id: str,
    ) -> Sequence[KnowledgeDocumentRecord]:
        statement = select(KnowledgeDocumentRecord).where(
            KnowledgeDocumentRecord.client_id == client_id,
            KnowledgeDocumentRecord.source_id == source_id,
        )
        return (await self._session.execute(statement)).scalars().all()

    async def list_page(
        self,
        client_id: str,
        source_id: str,
        *,
        after_path: str | None,
        limit: int,
    ) -> Sequence[KnowledgeDocumentRecord]:
        statement = select(KnowledgeDocumentRecord).where(
            KnowledgeDocumentRecord.client_id == client_id,
            KnowledgeDocumentRecord.source_id == source_id,
        )
        if after_path is not None:
            statement = statement.where(
                KnowledgeDocumentRecord.relative_path > after_path
            )
        statement = statement.order_by(KnowledgeDocumentRecord.relative_path).limit(limit)
        return (await self._session.execute(statement)).scalars().all()

    async def get(
        self,
        client_id: str,
        source_id: str,
        document_id: str,
    ) -> KnowledgeDocumentRecord | None:
        statement = select(KnowledgeDocumentRecord).where(
            KnowledgeDocumentRecord.client_id == client_id,
            KnowledgeDocumentRecord.source_id == source_id,
            KnowledgeDocumentRecord.id == document_id,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    def add(self, document: KnowledgeDocumentRecord) -> None:
        self._session.add(document)

    async def delete(self, document: KnowledgeDocumentRecord) -> None:
        await self._session.delete(document)


class KnowledgeChunkRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # 指定知识库的chunk
    async def list_for_source(
        self,
        client_id: str,
        source_id: str,
    ) -> Sequence[KnowledgeChunkRecord]:
        statement = select(KnowledgeChunkRecord).where(
            KnowledgeChunkRecord.client_id == client_id,
            KnowledgeChunkRecord.source_id == source_id,
        )
        return (await self._session.execute(statement)).scalars().all()

    def add(self, chunk: KnowledgeChunkRecord) -> None:
        self._session.add(chunk)

    async def delete(self, chunk: KnowledgeChunkRecord) -> None:
        await self._session.delete(chunk)

    async def search_keyword(
        self,
        client_id: str,
        query: str,
        *,
        source_id: str | None = None,
        limit: int = 10,
    ) -> list[KeywordChunkHit]:
        normalized_query = query.strip()
        if not normalized_query:
            return []
        match_query = build_fts_query(normalized_query)
        if match_query is None:
            where = "c.content LIKE :pattern"
            score = "0.0"
        else:
            where = "knowledge_chunks_fts MATCH :match_query"
            score = "-bm25(knowledge_chunks_fts, 0, 0, 0, 0, 2.0, 1.0)"
        statement = text(
            f"""SELECT c.id AS chunk_id, c.document_id, d.title, d.relative_path,
            c.heading_path, c.content, c.start_line, c.end_line, {score} AS score
            FROM knowledge_chunks_fts
            JOIN knowledge_chunks AS c ON c.id = knowledge_chunks_fts.chunk_id
            JOIN knowledge_documents AS d ON d.id = c.document_id
            WHERE knowledge_chunks_fts.client_id = :client_id
              AND (:source_id IS NULL OR knowledge_chunks_fts.source_id = :source_id)
              AND {where}
            ORDER BY score DESC, c.id
            LIMIT :limit"""
        )
        rows = (
            await self._session.execute(
                statement,
                {
                    "client_id": client_id,
                    "source_id": source_id,
                    "match_query": match_query,
                    "pattern": f"%{normalized_query}%",
                    "limit": limit,
                },
            )
        ).mappings()
        return [
            KeywordChunkHit(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                title=row["title"],
                relative_path=row["relative_path"],
                heading_path=tuple(json.loads(row["heading_path"])),
                content=row["content"],
                start_line=row["start_line"],
                end_line=row["end_line"],
                score=float(row["score"]),
            )
            for row in rows
        ]


class KnowledgeEmbeddingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_model(
        self,
        client_id: str,
        source_id: str,
        provider: str,
        model: str,
    ) -> Sequence[KnowledgeChunkEmbeddingRecord]:
        statement = select(KnowledgeChunkEmbeddingRecord).where(
            KnowledgeChunkEmbeddingRecord.client_id == client_id,
            KnowledgeChunkEmbeddingRecord.source_id == source_id,
            KnowledgeChunkEmbeddingRecord.provider == provider,
            KnowledgeChunkEmbeddingRecord.model == model,
        )
        return (await self._session.execute(statement)).scalars().all()

    def add(self, embedding: KnowledgeChunkEmbeddingRecord) -> None:
        self._session.add(embedding)
