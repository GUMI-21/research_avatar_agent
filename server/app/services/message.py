"""Transaction boundary for visible conversation Messages."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MessageRecord
from app.repositories import MessageRepository
from logs import log


class MessageService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = MessageRepository(session)

    # 存入对话记录
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
        message = await self._repository.append(
            client_id,
            session_id,
            agent_id,
            role=role,
            content=content,
            run_id=run_id,
        )
        try:
            await self._session.commit()
        except Exception as error:
            await self._session.rollback()
            log.warning(
                "db_mutation_rolled_back table=messages "
                "business=conversation_message action=create client_id={} "
                "session_id={} role={} error_type={}",
                client_id,
                session_id,
                role,
                type(error).__name__,
            )
            raise
        log.info(
            "db_mutation_committed table=messages business=conversation_message "
            "action=create client_id={} session_id={} message_id={} "
            "role={} sequence={}",
            client_id,
            session_id,
            message.id,
            role,
            message.sequence,
        )
        return message
