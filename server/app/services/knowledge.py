"""Validation and transaction boundary for local knowledge sources."""

from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgeSourceRecord
from app.repositories import KnowledgeSourceRepository
from logs import log


class KnowledgeSourcePathError(ValueError):
    pass


class KnowledgeSourceConflictError(ValueError):
    pass


def resolve_knowledge_root(raw_path: str) -> Path:
    try:
        root = Path(raw_path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as error:
        raise KnowledgeSourcePathError("Knowledge directory does not exist") from error
    if not root.is_dir():
        raise KnowledgeSourcePathError("Knowledge source must be a directory")
    if root == Path(root.anchor) or root == Path.home().resolve():
        raise KnowledgeSourcePathError("Knowledge directory is too broad")
    return root


class KnowledgeSourceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = KnowledgeSourceRepository(session)

    async def create(
        self,
        client_id: str,
        *,
        name: str,
        root_path: str,
        source_type: str = "obsidian",
    ) -> KnowledgeSourceRecord:
        normalized_root = str(resolve_knowledge_root(root_path))
        existing = await self._repository.get_by_root(client_id, normalized_root)
        if existing is not None:
            raise KnowledgeSourceConflictError("Knowledge directory already exists")
        try:
            source = await self._repository.create(
                client_id,
                name=name,
                root_path=normalized_root,
                source_type=source_type,
            )
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            raise KnowledgeSourceConflictError("Knowledge source name exists") from error
        log.info(
            "db_mutation_committed table=knowledge_sources "
            "business=knowledge_source action=create client_id={} source_id={}",
            client_id,
            source.id,
        )
        return source
