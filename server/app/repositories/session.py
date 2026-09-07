"""Client-scoped persistence operations for conversation Sessions."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRecord, SessionRecord


class SessionAgentNotFoundError(LookupError):
    pass

# 客户端对话框持久化
class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # “*”参数分隔，后面的参数必须用参数名调用
    async def create(
        self,
        client_id: str,
        agent_id: str,
        *,
        title: str = "New conversation",
    ) -> SessionRecord:
        agent_statement = select(AgentRecord.id).where(
            AgentRecord.client_id == client_id,
            AgentRecord.id == agent_id,
        )
        agent_result = await self._session.execute(agent_statement)
        if agent_result.scalar_one_or_none() is None:
            raise SessionAgentNotFoundError(agent_id)

        # 创建持久化对话
        conversation = SessionRecord(
            client_id=client_id,
            agent_id=agent_id,
            title=title,
        )
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    # 根据client_id查询所有对话
    async def list_sessions(self, client_id: str) -> Sequence[SessionRecord]:
        statement = (
            select(SessionRecord)
            .where(SessionRecord.client_id == client_id)
            .order_by(SessionRecord.created_at.desc())
        )
        result = await self._session.execute(statement)
        return result.scalars().all()

    # 查询单个对话
    async def get(self, client_id: str, session_id: str) -> SessionRecord | None:
        statement = select(SessionRecord).where(
            SessionRecord.client_id == client_id,
            SessionRecord.id == session_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
