"""Alembic environment backed by the application async database URL."""

import asyncio
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.database import Base
from app.core.settings import load_settings
from app.models import (  # noqa: F401
    AgentKnowledgeSourceRecord,
    AgentRecord,
    KnowledgeChunkEmbeddingRecord,
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
    MessageRecord,
    RunEventRecord,
    RunRecord,
    SessionRecord,
)

config = context.config
if not config.get_main_option("sqlalchemy.url"):
    environment = os.getenv("APP_ENV", "debug")
    config.set_main_option("sqlalchemy.url", load_settings(environment).database.url)

target_metadata = Base.metadata


def include_object(
    _object: object,
    name: str | None,
    type_: str,
    _reflected: bool,
    _compare_to: object | None,
) -> bool:
    if type_ == "table" and name and name.startswith("knowledge_chunks_fts"):
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def apply_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    engine = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(apply_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
