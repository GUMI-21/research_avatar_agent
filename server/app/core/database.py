"""Async database lifecycle shared by repository implementations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base metadata for application-owned relational models."""


class Database:
    """Own the engine and provide transaction-ready async sessions."""

    def __init__(self, url: str) -> None:
        self.engine = create_async_engine(url)
        # session创建工厂
        self.session_factory = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    @asynccontextmanager # 异步资源管理与释放，自动清理资源; AsyncIterator 异步迭代器
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            # yield 暂停
            yield session

    async def dispose(self) -> None:
        await self.engine.dispose()
