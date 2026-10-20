"""Client-scoped teaching state persistence; callers own validation and transactions."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TeachingSessionRecord
from app.repositories.session import SessionRepository
from app.schemas.teaching import CourseSelection
from logs import log


class TeachingSessionNotFoundError(LookupError):
    pass


class TeachingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        client_id: str,
        session_id: str,
        *,
        selection: CourseSelection,
        course_version: str,
    ) -> TeachingSessionRecord:
        # 不仅检查外键存在，还要防止绑定其他客户端的对话。
        if await SessionRepository(self._session).get(client_id, session_id) is None:
            raise TeachingSessionNotFoundError("Session not found")
        record = TeachingSessionRecord(
            client_id=client_id,
            session_id=session_id,
            course_id=selection.course_id,
            lesson_id=selection.lesson_id,
            course_version=course_version,
        )
        self._session.add(record)
        await self._session.flush()
        log.info(
            "db_mutation_staged table=teaching_session_states business=avatar_teaching "
            "action=create client_id={} session_id={}",
            client_id, session_id,
        )
        return record

    async def get(self, client_id: str, session_id: str) -> TeachingSessionRecord | None:
        statement = select(TeachingSessionRecord).where(
            TeachingSessionRecord.client_id == client_id,
            TeachingSessionRecord.session_id == session_id,
        )
        return (await self._session.execute(statement)).scalar_one_or_none()
