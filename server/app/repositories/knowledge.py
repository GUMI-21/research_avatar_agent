"""Client-scoped persistence for local knowledge sources."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeSourceRecord


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
