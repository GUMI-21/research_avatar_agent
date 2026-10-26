"""Course resources and HTTP teaching over the shared Agent execution service."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import ClientID, DBSession
from app.api.errors import llm_http_exception
from app.adapters.llm.errors import LLMConfigurationError, LLMError
from app.repositories import TeachingRepository, TeachingSessionNotFoundError
from app.schemas.teaching import (
    CourseListResponse, CourseRead, CourseSelection, TeachingSessionRead,
    TeachingChatRequest, TeachingChatResponse,
)
from app.services.courses import CourseCatalog, CourseSelectionNotFoundError
from app.services.teaching import TeachingBindingConflictError, TeachingService
from app.services.session_run_guard import SessionRunBusyError
from app.services.run_execution import RunExecutionParentNotFoundError, RunExecutionService
from app.services.runtime_registry import RuntimeNotFoundError
from app.services.teaching_chat import TeachingChatService
from app.services.teaching_output import TeachingOutputError
from logs import log

router = APIRouter(prefix="/avatar")


def get_course_catalog(request: Request) -> CourseCatalog:
    return cast(CourseCatalog, request.app.state.course_catalog)


Courses = Annotated[CourseCatalog, Depends(get_course_catalog)]


def get_teaching_execution(http_request: Request, database_session: DBSession) -> RunExecutionService:
    state = http_request.app.state
    if any(getattr(state, name, None) is None for name in ("runtime_registry", "course_catalog", "session_run_guard")):
        raise HTTPException(status_code=503, detail="Teaching execution is unavailable")
    return RunExecutionService(
        database_session, state.runtime_registry,
        getattr(state, "embedding_client", None), getattr(state, "graph_checkpointer", None),
        getattr(state, "skill_catalog", None), state.course_catalog, state.session_run_guard,
    )


@router.post("/chat", response_model=TeachingChatResponse)
async def teaching_chat(
    request: TeachingChatRequest, client_id: ClientID,
    execution: Annotated[RunExecutionService, Depends(get_teaching_execution)],
) -> TeachingChatResponse:
    try:
        return await TeachingChatService(execution).respond(client_id, request)
    except (TeachingSessionNotFoundError, RunExecutionParentNotFoundError, CourseSelectionNotFoundError) as error:
        raise HTTPException(status_code=404, detail="Teaching session or course is unavailable") from error
    except (SessionRunBusyError, TeachingBindingConflictError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RuntimeNotFoundError as error:
        raise HTTPException(status_code=503, detail="Agent runtime is unavailable") from error
    except TeachingOutputError:
        raise HTTPException(status_code=502, detail="Invalid teaching model output") from None
    except LLMConfigurationError:
        raise HTTPException(status_code=400, detail="LLM configuration is invalid or incomplete") from None
    except LLMError as error:
        raise llm_http_exception(error) from None
    except Exception as error:
        log.warning("teaching_chat_failed business=avatar_teaching client_id={} session_id={} error_type={}",
                    client_id, request.session_id, type(error).__name__)
        raise HTTPException(status_code=500, detail="Teaching execution failed") from None


@router.get("/courses", response_model=CourseListResponse)
async def list_courses(_client_id: ClientID, catalog: Courses) -> CourseListResponse:
    # 显式响应字段，不能直接序列化含脚本正文的内部 CourseDefinition。
    return CourseListResponse(courses=[CourseRead.model_validate(item) for item in catalog.list()])


@router.get("/sessions/{session_id}/teaching", response_model=TeachingSessionRead)
async def get_teaching(
    session_id: str, client_id: ClientID, database_session: DBSession,
) -> TeachingSessionRead:
    record = await TeachingRepository(database_session).get(client_id, session_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Teaching configuration not found")
    return TeachingSessionRead.model_validate(record)


@router.put("/sessions/{session_id}/teaching", response_model=TeachingSessionRead)
async def bind_teaching(
    session_id: str, request: CourseSelection, client_id: ClientID,
    database_session: DBSession, catalog: Courses, http_request: Request,
) -> TeachingSessionRead:
    try:
        guard = getattr(http_request.app.state, "session_run_guard", None)
        if guard is None:
            raise HTTPException(status_code=503, detail="Session Run guard is unavailable")
        async with guard.claim(client_id, session_id):
            record = await TeachingService(database_session, catalog).bind(client_id, session_id, request)
    except (TeachingSessionNotFoundError, CourseSelectionNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (TeachingBindingConflictError, SessionRunBusyError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TeachingSessionRead.model_validate(record)
