"""FastAPI dependencies shared by public routes."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.knowledge import EmbeddingClient
from app.core.database import Database
from app.services.llm_runtime import LLMRuntime


def get_llm_runtime(request: Request) -> LLMRuntime:
    """Return the application-scoped runtime LLM client."""
    return request.app.state.llm_runtime


def get_embedding_client(request: Request) -> EmbeddingClient:
    """Return the application-scoped local embedding engine."""
    return request.app.state.embedding_client


async def get_db_session(request: Request) -> AsyncIterator[AsyncSession]:
    database: Database = request.app.state.database
    async with database.session() as session:
        yield session

# 根据请求头获取client_id
def get_client_id(
    x_client_id: Annotated[
        str,
        Header(alias="X-Client-ID", min_length=1, max_length=64),
    ],
) -> str:
    """Resolve the temporary local client scope; authentication comes later."""
    client_id = x_client_id.strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Client-ID must not be blank",
        )
    return client_id

# Annotated[参数类型, Depends(获取参数方法)]
DBSession = Annotated[AsyncSession, Depends(get_db_session)]
ClientID = Annotated[str, Depends(get_client_id)]
EmbeddingEngine = Annotated[EmbeddingClient, Depends(get_embedding_client)]
