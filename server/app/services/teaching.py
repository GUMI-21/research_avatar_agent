"""Validate initial teaching bindings; execution and progress updates come later."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import TeachingSessionRecord
from app.repositories import (
    AgentRepository, SessionRepository, TeachingRepository, TeachingSessionNotFoundError,
)
from app.schemas.teaching import CourseSelection
from app.services.courses import CourseCatalog
from logs import log


class TeachingBindingConflictError(ValueError):
    pass


class TeachingService:
    def __init__(self, session: AsyncSession, catalog: CourseCatalog) -> None:
        self._session = session
        self._catalog = catalog

    # 把课程、课节绑定到一个 Agent 的对话会话（Session）
    async def bind(
        self, client_id: str, session_id: str, selection: CourseSelection,
    ) -> TeachingSessionRecord:
        conversation = await SessionRepository(self._session).get(client_id, session_id)
        if conversation is None:
            raise TeachingSessionNotFoundError("Session not found")
        agent = await AgentRepository(self._session).get(client_id, conversation.agent_id)
        if agent is None:
            raise TeachingSessionNotFoundError("Session not found")
        if agent.runtime != "native":
            raise TeachingBindingConflictError("Teaching requires a Native Agent")
        course = self._catalog.resolve(selection)
        repository = TeachingRepository(self._session)
        existing = await repository.get(client_id, session_id)
        if existing is not None:
            if (existing.course_id, existing.lesson_id, existing.course_version) != (
                course.id, selection.lesson_id, course.version_hash,
            ):
                # 先禁止切课/升级，不能静默重置进度或改写运行中的版本。
                raise TeachingBindingConflictError("Rebinding or script upgrades are not supported yet")
            return existing
        try:
            record = await repository.create(
                client_id, session_id, selection=selection, course_version=course.version_hash,
            )
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise TeachingBindingConflictError("Teaching binding conflicted; retry the request") from error
        except Exception:
            await self._session.rollback()
            raise
        log.info(
            "db_mutation_committed table=teaching_session_states business=avatar_teaching "
            "action=bind client_id={} session_id={}", client_id, session_id,
        )
        return record
