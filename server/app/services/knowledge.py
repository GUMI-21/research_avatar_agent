"""Validation, synchronization, and transactions for local knowledge sources."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.knowledge import (
    ParsedMarkdownDocument,
    ScannedMarkdownFile,
    parse_markdown,
    scan_markdown_files,
)
from app.models import KnowledgeDocumentRecord, KnowledgeSourceRecord
from app.models.agent import utc_now
from app.repositories import KnowledgeDocumentRepository, KnowledgeSourceRepository
from logs import log


class KnowledgeSourcePathError(ValueError):
    pass


class KnowledgeSourceConflictError(ValueError):
    pass


class KnowledgeSourceNotFoundError(LookupError):
    pass


class KnowledgeSourceSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class KnowledgeSyncResult:
    scanned: int
    created: int
    updated: int
    deleted: int
    unchanged: int


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


def _read_documents(
    root: Path,
) -> list[tuple[ScannedMarkdownFile, ParsedMarkdownDocument]]:
    documents: list[tuple[ScannedMarkdownFile, ParsedMarkdownDocument]] = []
    for scanned in scan_markdown_files(root):
        parsed = parse_markdown(
            scanned.relative_path,
            scanned.path.read_text(encoding="utf-8"),
        )
        documents.append((scanned, parsed))
    return documents


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

    # 根据目录同步本地知识库
    async def sync(self, client_id: str, source_id: str) -> KnowledgeSyncResult:
        source = await self._repository.get(client_id, source_id)
        if source is None:
            raise KnowledgeSourceNotFoundError("Knowledge source not found")
        source.sync_status = "syncing"
        source.error_message = None
        await self._session.commit()

        documents = KnowledgeDocumentRepository(self._session)
        try:
            parsed_files = await asyncio.to_thread(
                _read_documents,
                resolve_knowledge_root(source.root_path),
            )
            existing = {
                item.relative_path: item
                for item in await documents.list_for_source(client_id, source.id)
            }
            created = updated = unchanged = 0
            for scanned, parsed in parsed_files:
                record = existing.pop(scanned.relative_path, None)
                if record is not None and record.content_hash == scanned.content_hash:
                    unchanged += 1
                    continue
                if record is None:
                    record = KnowledgeDocumentRecord(
                        client_id=client_id,
                        source_id=source.id,
                        relative_path=scanned.relative_path,
                        title=parsed.title,
                        content_hash=scanned.content_hash,
                        frontmatter=parsed.frontmatter,
                        source_modified_at=scanned.source_modified_at,
                    )
                    documents.add(record)
                    created += 1
                else:
                    record.title = parsed.title
                    record.content_hash = scanned.content_hash
                    record.frontmatter = parsed.frontmatter
                    record.source_modified_at = scanned.source_modified_at
                    record.indexed_at = None
                    updated += 1
            for deleted_record in existing.values():
                await documents.delete(deleted_record)
            source.sync_status = "ready"
            source.last_synced_at = utc_now()
            await self._session.commit()
        except Exception as error:
            await self._session.rollback()
            failed_source = await self._repository.get(client_id, source_id)
            if failed_source is not None:
                failed_source.sync_status = "failed"
                failed_source.error_message = str(error)
                await self._session.commit()
            log.warning(
                "db_mutation_rolled_back table=knowledge_documents "
                "business=knowledge_sync client_id={} source_id={} error_type={}",
                client_id,
                source_id,
                type(error).__name__,
            )
            raise KnowledgeSourceSyncError("Knowledge source sync failed") from error

        result = KnowledgeSyncResult(
            scanned=len(parsed_files),
            created=created,
            updated=updated,
            deleted=len(existing),
            unchanged=unchanged,
        )
        log.info(
            "db_mutation_committed table=knowledge_documents "
            "business=knowledge_sync client_id={} source_id={} result={}",
            client_id,
            source_id,
            result,
        )
        return result
