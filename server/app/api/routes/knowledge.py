"""Client-scoped local knowledge source routes."""

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

from app.api.dependencies import ClientID, DBSession
from app.repositories import KnowledgeDocumentRepository, KnowledgeSourceRepository
from app.schemas.knowledge import (
    KnowledgeDocumentListResponse,
    KnowledgeDocumentRead,
    KnowledgeSourceCreate,
    KnowledgeSourceListResponse,
    KnowledgeSourceRead,
    KnowledgeSyncResponse,
)
from app.services import (
    KnowledgeSourceConflictError,
    KnowledgeSourceNotFoundError,
    KnowledgeSourcePathError,
    KnowledgeSourceService,
    KnowledgeSourceSyncError,
)

router = APIRouter(prefix="/knowledge/sources")

# 保存知识库路径
@router.post(
    "",
    response_model=KnowledgeSourceRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_knowledge_source(
    request: KnowledgeSourceCreate,
    client_id: ClientID,
    database_session: DBSession,
) -> KnowledgeSourceRead:
    try:
        source = await KnowledgeSourceService(database_session).create(
            client_id,
            **request.model_dump(),
        )
    except KnowledgeSourcePathError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except KnowledgeSourceConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return KnowledgeSourceRead.model_validate(source)


@router.get("", response_model=KnowledgeSourceListResponse)
async def list_knowledge_sources(
    client_id: ClientID,
    database_session: DBSession,
) -> KnowledgeSourceListResponse:
    sources = await KnowledgeSourceRepository(database_session).list_sources(
        client_id
    )
    return KnowledgeSourceListResponse(
        sources=[KnowledgeSourceRead.model_validate(source) for source in sources]
    )


@router.get("/{source_id}", response_model=KnowledgeSourceRead)
async def get_knowledge_source(
    source_id: str,
    client_id: ClientID,
    database_session: DBSession,
) -> KnowledgeSourceRead:
    source = await KnowledgeSourceRepository(database_session).get(
        client_id,
        source_id,
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        )
    return KnowledgeSourceRead.model_validate(source)


# 手动更新知识库
@router.post("/{source_id}/sync", response_model=KnowledgeSyncResponse)
async def sync_knowledge_source(
    source_id: str,
    client_id: ClientID,
    database_session: DBSession,
) -> KnowledgeSyncResponse:
    try:
        result = await KnowledgeSourceService(database_session).sync(
            client_id,
            source_id,
        )
    except KnowledgeSourceNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except KnowledgeSourceSyncError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error
    return KnowledgeSyncResponse(source_id=source_id, **asdict(result))


# 展示知识库文档
@router.get(
    "/{source_id}/documents",
    response_model=KnowledgeDocumentListResponse,
)
async def list_knowledge_documents(
    source_id: str,
    client_id: ClientID,
    database_session: DBSession,
    after_path: Annotated[str | None, Query(max_length=1024)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> KnowledgeDocumentListResponse:
    source = await KnowledgeSourceRepository(database_session).get(client_id, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge source not found")
    records = list(
        await KnowledgeDocumentRepository(database_session).list_page(
            client_id,
            source_id,
            after_path=after_path,
            limit=limit + 1,
        )
    )
    has_more = len(records) > limit
    records = records[:limit]
    return KnowledgeDocumentListResponse(
        documents=[KnowledgeDocumentRead.model_validate(record) for record in records],
        next_cursor=records[-1].relative_path if has_more else None,
        has_more=has_more,
    )


@router.get(
    "/{source_id}/documents/{document_id}",
    response_model=KnowledgeDocumentRead,
)
async def get_knowledge_document(
    source_id: str,
    document_id: str,
    client_id: ClientID,
    database_session: DBSession,
) -> KnowledgeDocumentRead:
    document = await KnowledgeDocumentRepository(database_session).get(
        client_id,
        source_id,
        document_id,
    )
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Knowledge document not found")
    return KnowledgeDocumentRead.model_validate(document)
