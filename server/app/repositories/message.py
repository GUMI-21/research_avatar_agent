"""Client-scoped persistence operations for conversation Messages."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRecord, MessageRecord, SessionRecord


class MessageParentNotFoundError(LookupError):
    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(f"{resource} not found")


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # 添加对话记录
    async def append(
        self,
        client_id: str,
        session_id: str,
        agent_id: str,
        *,
        role: str,
        content: str,
        run_id: str | None = None,
    ) -> MessageRecord:
        session_statement = select(SessionRecord.id).where(
            SessionRecord.client_id == client_id,
            SessionRecord.id == session_id,
        )
        if (await self._session.execute(session_statement)).scalar_one_or_none() is None:
            raise MessageParentNotFoundError("Session")

        agent_statement = select(AgentRecord.id).where(
            AgentRecord.client_id == client_id,
            AgentRecord.id == agent_id,
        )
        if (await self._session.execute(agent_statement)).scalar_one_or_none() is None:
            raise MessageParentNotFoundError("Agent")

        sequence_statement = select(
            func.coalesce(func.max(MessageRecord.sequence), 0) + 1
        ).where(
            MessageRecord.client_id == client_id,
            MessageRecord.session_id == session_id,
        )
        sequence = (await self._session.execute(sequence_statement)).scalar_one()
        message = MessageRecord(
            client_id=client_id,
            session_id=session_id,
            agent_id=agent_id,
            run_id=run_id,
            role=role,
            content=content,
            sequence=sequence,
        )
        self._session.add(message)
        await self._session.flush()
        return message

    # 获取当前对话历史记录
    async def list_messages(
        self,
        client_id: str,
        session_id: str,
        *,
        before_sequence: int | None = None,
        limit: int = 50,
    ) -> Sequence[MessageRecord]:
        statement = select(MessageRecord).where(
            MessageRecord.client_id == client_id,
            MessageRecord.session_id == session_id,
        )
        if before_sequence is not None:
            statement = statement.where(MessageRecord.sequence < before_sequence)
        statement = statement.order_by(MessageRecord.sequence.desc()).limit(limit)
        result = await self._session.execute(statement)
        messages = list(result.scalars().all())
        messages.reverse()
        return messages
