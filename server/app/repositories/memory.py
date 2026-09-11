"""Persistence operations for client-scoped Agent memories."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentMemoryRecord, AgentRecord


class MemoryParentNotFoundError(LookupError):
    pass


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, client_id: str, agent_id: str, content: str) -> AgentMemoryRecord:
        exists = await self._session.scalar(select(AgentRecord.id).where(
            AgentRecord.client_id == client_id, AgentRecord.id == agent_id
        ))
        if exists is None:
            raise MemoryParentNotFoundError(agent_id)
        record = AgentMemoryRecord(client_id=client_id, agent_id=agent_id, content=content)
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_for_agent(
        self, client_id: str, agent_id: str, *, enabled_only: bool = False
    ) -> Sequence[AgentMemoryRecord]:
        statement = select(AgentMemoryRecord).where(
            AgentMemoryRecord.client_id == client_id,
            AgentMemoryRecord.agent_id == agent_id,
        )
        if enabled_only:
            statement = statement.where(AgentMemoryRecord.enabled.is_(True))
        result = await self._session.execute(statement.order_by(AgentMemoryRecord.created_at.desc()))
        return result.scalars().all()

    async def get(self, client_id: str, agent_id: str, memory_id: str) -> AgentMemoryRecord | None:
        return await self._session.scalar(select(AgentMemoryRecord).where(
            AgentMemoryRecord.client_id == client_id,
            AgentMemoryRecord.agent_id == agent_id,
            AgentMemoryRecord.id == memory_id,
        ))
