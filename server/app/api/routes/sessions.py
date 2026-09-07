"""Client-scoped conversation Session resource routes."""

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import ClientID, DBSession
from app.repositories import SessionAgentNotFoundError, SessionRepository
from app.schemas.session import SessionCreate, SessionListResponse, SessionRead

router = APIRouter(prefix="/sessions")

# 创建会话
@router.post("", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: SessionCreate,
    client_id: ClientID,
    database_session: DBSession,
) -> SessionRead:
    try:
        conversation = await SessionRepository(database_session).create(
            client_id,
            **request.model_dump(),
        )
        await database_session.commit()
    except SessionAgentNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        ) from error
    return SessionRead.model_validate(conversation)

# 获取所有会话
@router.get("", response_model=SessionListResponse)
async def list_sessions(
    client_id: ClientID,
    database_session: DBSession,
) -> SessionListResponse:
    sessions = await SessionRepository(database_session).list_sessions(client_id)
    return SessionListResponse(
        sessions=[SessionRead.model_validate(item) for item in sessions]
    )

# 查询具体会话
@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: str,
    client_id: ClientID,
    database_session: DBSession,
) -> SessionRead:
    conversation = await SessionRepository(database_session).get(
        client_id,
        session_id,
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )
    return SessionRead.model_validate(conversation)
