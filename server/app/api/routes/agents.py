"""Client-scoped Agent resource routes."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import ClientID, DBSession
from app.repositories import AgentRepository
from app.schemas.agent import AgentCreate, AgentListResponse, AgentRead

router = APIRouter(prefix="/agents")


# 添加agent
@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: AgentCreate,
    client_id: ClientID,
    session: DBSession,
) -> AgentRead:
    repository = AgentRepository(session)
    try:
        agent = await repository.create(
            client_id,
            # 展开字典
            **request.model_dump(),
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent name already exists",
        ) from error
    return AgentRead.model_validate(agent)

# 获取当前agent_list
@router.get("", response_model=AgentListResponse)
async def list_agents(
    client_id: ClientID,
    session: DBSession,
) -> AgentListResponse:
    agents = await AgentRepository(session).list_agents(client_id)
    return AgentListResponse(
        agents=[
            AgentRead.model_validate(agent)
            for agent in agents
        ]
    )

# 限定agent_id查询
@router.get("/{agent_id}", response_model=AgentRead)
async def get_agent(
    agent_id: str,
    client_id: ClientID,
    session: DBSession,
) -> AgentRead:
    agent = await AgentRepository(session).get(client_id, agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return AgentRead.model_validate(agent)
