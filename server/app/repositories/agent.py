"""Client-scoped persistence operations for Agent records."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentKnowledgeSourceRecord, AgentRecord, KnowledgeSourceRecord


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        client_id: str,
        *,
        name: str,
        system_prompt: str,
        runtime: str = "native",
        model: str | None = None,
        knowledge_sources: Sequence[KnowledgeSourceRecord] = (),
    ) -> AgentRecord:
        agent = AgentRecord(
            client_id=client_id,
            name=name,
            system_prompt=system_prompt,
            runtime=runtime,
            model=model,
            # 绑定知识库
            knowledge_links=[
                AgentKnowledgeSourceRecord(
                    client_id=client_id,
                    source_id=source.id,
                )
                for source in knowledge_sources
            ],
        )
        self._session.add(agent)
        await self._session.flush()
        return agent

    # Sequence: 数据序列
    async def list_agents(self, client_id: str) -> Sequence[AgentRecord]:
        statement = (
            select(AgentRecord)
            .where(AgentRecord.client_id == client_id)
            .order_by(AgentRecord.created_at.desc())
        )
        result = await self._session.execute(statement)
        # 取出所有记录收集为列表
        return result.scalars().all()

    async def get(self, client_id: str, agent_id: str) -> AgentRecord | None:
        statement = select(AgentRecord).where(
            AgentRecord.client_id == client_id,
            AgentRecord.id == agent_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
