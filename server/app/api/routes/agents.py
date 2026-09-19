"""Client-scoped Agent resource routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import ClientID, DBSession
from app.repositories import AgentRepository
from app.api.routes.skills import get_skill_catalog
from app.schemas.agent import (
    AgentCreate,
    AgentListResponse,
    AgentRead,
    AgentSkillsUpdate,
    AgentUpdate,
)
from app.services import AgentKnowledgeSourceNotFoundError, AgentService
from app.services.skills import SkillCatalog

router = APIRouter(prefix="/agents")


# 添加agent
@router.post("", response_model=AgentRead, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: AgentCreate,
    client_id: ClientID,
    session: DBSession,
) -> AgentRead:
    try:
        agent = await AgentService(session).create(
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
    except AgentKnowledgeSourceNotFoundError as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source not found",
        ) from error
    return AgentRead.model_validate(agent)


@router.patch("/{agent_id}", response_model=AgentRead)
async def update_agent(
    agent_id: str,
    request: AgentUpdate,
    client_id: ClientID,
    session: DBSession,
) -> AgentRead:
    try:
        agent = await AgentRepository(session).update(
            client_id, agent_id, request.model_dump(exclude_unset=True)
        )
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Agent name already exists") from error
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


@router.put("/{agent_id}/skills", response_model=AgentRead)
async def replace_agent_skills(
    agent_id: str,
    request: AgentSkillsUpdate,
    client_id: ClientID,
    session: DBSession,
    catalog: Annotated[SkillCatalog, Depends(get_skill_catalog)],
) -> AgentRead:
    missing = next(
        (skill_id for skill_id in request.skill_ids if catalog.get(skill_id) is None),
        None,
    )
    if missing is not None:
        raise HTTPException(status_code=404, detail="Skill not found")
    agent = await AgentRepository(session).replace_skills(
        client_id, agent_id, request.skill_ids
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    await session.commit()
    return AgentRead.model_validate(agent)
