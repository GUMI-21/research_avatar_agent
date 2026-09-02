"""Client-scoped persistence for local knowledge sources."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
)


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
