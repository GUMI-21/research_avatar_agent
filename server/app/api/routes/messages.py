"""Read-only conversation Message history routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import ClientID, DBSession
from app.repositories import MessageRepository, SessionRepository
from app.schemas.message import MessageListResponse, MessageRead

router = APIRouter(prefix="/sessions/{session_id}/messages")

# 获取对话框对话记录
@router.get("", response_model=MessageListResponse)
async def list_messages(
    session_id: str,
    client_id: ClientID,
    database_session: DBSession,
    # int 或 None，来自于Url参数query，大于0，默认None
    before_sequence: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> MessageListResponse:
    conversation = await SessionRepository(database_session).get(
        client_id,
        session_id,
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    records = list(
        await MessageRepository(database_session).list_messages(
            client_id,
            session_id,
            before_sequence=before_sequence,
            # 多查一个来处理has_more
            limit=limit + 1,
        )
    )
    has_more = len(records) > limit
    if has_more:
        records = records[1:]
    return MessageListResponse(
        messages=[MessageRead.model_validate(record) for record in records],
        next_cursor=records[0].sequence if has_more else None,
        has_more=has_more,
    )
