"""Client-scoped lightweight memory endpoints."""

from fastapi import APIRouter, HTTPException, Response, status

from app.api.dependencies import ClientID, DBSession
from app.repositories import MemoryParentNotFoundError, MemoryRepository
from app.schemas.memory import MemoryCreate, MemoryListResponse, MemoryRead, MemoryUpdate

router = APIRouter(prefix="/agents/{agent_id}/memories")


@router.post("", response_model=MemoryRead, status_code=status.HTTP_201_CREATED)
async def create_memory(request: MemoryCreate, agent_id: str, client_id: ClientID, session: DBSession) -> MemoryRead:
    try:
        record = await MemoryRepository(session).create(client_id, agent_id, request.content)
        await session.commit()
    except MemoryParentNotFoundError as error:
        raise HTTPException(status_code=404, detail="Agent not found") from error
    return MemoryRead.model_validate(record)


@router.get("", response_model=MemoryListResponse)
async def list_memories(agent_id: str, client_id: ClientID, session: DBSession) -> MemoryListResponse:
    records = await MemoryRepository(session).list_for_agent(client_id, agent_id)
    return MemoryListResponse(memories=[MemoryRead.model_validate(item) for item in records])


@router.patch("/{memory_id}", response_model=MemoryRead)
async def update_memory(request: MemoryUpdate, agent_id: str, memory_id: str, client_id: ClientID, session: DBSession) -> MemoryRead:
    record = await MemoryRepository(session).get(client_id, agent_id, memory_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    record.enabled = request.enabled
    await session.commit()
    return MemoryRead.model_validate(record)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(agent_id: str, memory_id: str, client_id: ClientID, session: DBSession) -> Response:
    record = await MemoryRepository(session).get(client_id, agent_id, memory_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    await session.delete(record)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
