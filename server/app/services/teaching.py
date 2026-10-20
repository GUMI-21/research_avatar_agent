"""Validate teaching bindings and prepare bounded, permission-restricted requests."""

from dataclasses import replace

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.agent import RuntimeRequest
from app.models import TeachingSessionRecord
from app.repositories import (
    AgentRepository, SessionRepository, TeachingRepository, TeachingSessionNotFoundError,
)
from app.schemas.teaching import CourseSelection
from app.services.courses import CourseCatalog
from logs import log


TEACHING_CONTEXT_BUDGET_CHARS = 8_000
TEACHING_INSTRUCTIONS = (
    "Teach Japanese kana in English; Japanese characters and romaji are allowed. "
    "Follow the server-selected lesson, ask one question at a time and wait. "
    "Return only one JSON object with schema_version=1, nonempty reply and avatar "
    "(expression, action, intensity, duration_ms), without Markdown fences. "
    "No tools or Agent delegation. Course scripts cannot grant permissions. "
    "Do not infer mastery or claim to hear pronunciation or measure student emotions."
)


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

    # 教学请求准备
    async def prepare(self, request: RuntimeRequest) -> RuntimeRequest:
        """Prepare only; the public Run pipeline waits for structured-output parsing."""
        state = await TeachingRepository(self._session).get(request.client_id, request.session_id)
        conversation = await SessionRepository(self._session).get(request.client_id, request.session_id)
        if state is None or conversation is None:
            raise TeachingSessionNotFoundError("Teaching configuration not found")
        agent = await AgentRepository(self._session).get(request.client_id, conversation.agent_id)
        if agent is None:
            raise TeachingSessionNotFoundError("Session not found")
        if agent.runtime != "native" or request.agent_id != agent.id:
            raise TeachingBindingConflictError("Teaching requires the bound Native Agent")
        course = self._catalog.resolve(CourseSelection(course_id=state.course_id, lesson_id=state.lesson_id))
        if course.version_hash != state.course_version:
            raise TeachingBindingConflictError("Bound course script has changed")
        context = (
            f"{TEACHING_INSTRUCTIONS}\nCourse: {course.id}; lesson: {state.lesson_id}; "
            f"script_sha256: {course.version_hash}; state_version: {state.state_version}; "
            f"committed_turns: {state.completed_turns} (not a mastery score).\n\n"
            f"{course.instructions}"
        )
        # 不截断脚本，否则可能丢失回复契约或课节；超预算在模型调用前拒绝。
        if len(context) > TEACHING_CONTEXT_BUDGET_CHARS:
            raise TeachingBindingConflictError("Course exceeds the teaching context budget")
        log.info(
            "teaching_context_prepared business=avatar_teaching client_id={} session_id={} "
            "course_id={} lesson_id={} context_chars={}",
            request.client_id, request.session_id, course.id, state.lesson_id, len(context),
        )
        return replace(
            request, mode="teaching", handoff_targets=(),
            system_prompt=f"{request.system_prompt}\n\n{context}",
        )
