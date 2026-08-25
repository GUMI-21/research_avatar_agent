"""Client-scoped Agent resource routes."""

from fastapi import APIRouter, status

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
    agent = await repository.create(
        client_id,
        # 展开字典
        **request.model_dump(),
    )
    await session.commit()
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
