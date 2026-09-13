"""Client-scoped external runtime thread persistence."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RuntimeThreadRecord


class RuntimeThreadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_external_id(
        self,
        client_id: str,
        session_id: str,
        agent_id: str,
        runtime: str,
    ) -> str | None:
        statement = select(RuntimeThreadRecord.external_thread_id).where(
            RuntimeThreadRecord.client_id == client_id,
            RuntimeThreadRecord.session_id == session_id,
            RuntimeThreadRecord.agent_id == agent_id,
            RuntimeThreadRecord.runtime == runtime,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()

    async def set_external_id(
        self,
        client_id: str,
        session_id: str,
        agent_id: str,
        runtime: str,
        external_thread_id: str,
    ) -> RuntimeThreadRecord:
        statement = select(RuntimeThreadRecord).where(
            RuntimeThreadRecord.client_id == client_id,
            RuntimeThreadRecord.session_id == session_id,
            RuntimeThreadRecord.agent_id == agent_id,
            RuntimeThreadRecord.runtime == runtime,
        )
        record = (await self._session.execute(statement)).scalar_one_or_none()
        if record is None:
            record = RuntimeThreadRecord(
                client_id=client_id,
                session_id=session_id,
                agent_id=agent_id,
                runtime=runtime,
                external_thread_id=external_thread_id,
            )
            self._session.add(record)
        else:
            record.external_thread_id = external_thread_id
        await self._session.flush()
        return record
