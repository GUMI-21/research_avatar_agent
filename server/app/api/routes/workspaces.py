"""Local workspace identity routes."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DBSession
from app.models.workspace import WorkspaceRecord
from app.schemas.workspace import USERNAME_PATTERN, WorkspaceCreate, WorkspaceRead

router = APIRouter(prefix="/workspaces")

# 根据用户名隔离数据
@router.post("", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreate, session: DBSession
) -> WorkspaceRead:
    record = WorkspaceRecord(username=request.username)
    session.add(record)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Username already exists") from error
    return WorkspaceRead.model_validate(record)


@router.get("/{username}", response_model=WorkspaceRead)
async def get_workspace(
    username: Annotated[str, Path(min_length=1, max_length=64, pattern=USERNAME_PATTERN)],
    session: DBSession,
) -> WorkspaceRead:
    record = await session.get(WorkspaceRecord, username.lower())
    if record is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceRead.model_validate(record)
