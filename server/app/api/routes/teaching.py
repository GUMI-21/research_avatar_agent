"""Course metadata and client-scoped initial teaching bindings, without LLM calls."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.dependencies import ClientID, DBSession
from app.repositories import TeachingRepository, TeachingSessionNotFoundError
from app.schemas.teaching import (
    CourseListResponse, CourseRead, CourseSelection, TeachingSessionRead,
)
from app.services.courses import CourseCatalog, CourseSelectionNotFoundError
from app.services.teaching import TeachingBindingConflictError, TeachingService

router = APIRouter(prefix="/avatar")


def get_course_catalog(request: Request) -> CourseCatalog:
    return cast(CourseCatalog, request.app.state.course_catalog)


Courses = Annotated[CourseCatalog, Depends(get_course_catalog)]


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
    database_session: DBSession, catalog: Courses,
) -> TeachingSessionRead:
    try:
        record = await TeachingService(database_session, catalog).bind(client_id, session_id, request)
    except (TeachingSessionNotFoundError, CourseSelectionNotFoundError) as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except TeachingBindingConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TeachingSessionRead.model_validate(record)
