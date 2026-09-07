"""Validation, synchronization, and transactions for local knowledge sources."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.knowledge import (
    MarkdownChunk,
    ParsedMarkdownDocument,
    ScannedMarkdownFile,
    chunk_markdown,
    parse_markdown,
    scan_markdown_files,
)
from app.models import (
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
)
from app.models.agent import utc_now
from app.repositories import (
    KnowledgeChunkRepository,
    KnowledgeDocumentRepository,
    KnowledgeSourceRepository,
)
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
    chunks: int


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
) -> list[tuple[ScannedMarkdownFile, ParsedMarkdownDocument, list[MarkdownChunk]]]:
    documents = []
    for scanned in scan_markdown_files(root):
        raw_text = scanned.path.read_text(encoding="utf-8")
        parsed = parse_markdown(
            scanned.relative_path,
            raw_text,
        )
        documents.append((scanned, parsed, chunk_markdown(raw_text)))
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
        chunks = KnowledgeChunkRepository(self._session)
        try:
            parsed_files = await asyncio.to_thread(
                _read_documents,
                resolve_knowledge_root(source.root_path),
            )
            existing = {
                item.relative_path: item
                for item in await documents.list_for_source(client_id, source.id)
            }
            existing_chunks: dict[str, list[KnowledgeChunkRecord]] = {}
            for chunk in await chunks.list_for_source(client_id, source.id):
                existing_chunks.setdefault(chunk.document_id, []).append(chunk)
            created = updated = unchanged = 0
            rebuild: list[tuple[KnowledgeDocumentRecord, list[MarkdownChunk]]] = []
            for scanned, parsed, parsed_chunks in parsed_files:
                record = existing.pop(scanned.relative_path, None)
                if (
                    record is not None
                    and record.content_hash == scanned.content_hash
                    and record.indexed_at is not None
                ):
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
                record.indexed_at = utc_now()
                rebuild.append((record, parsed_chunks))
            await self._session.flush()
            for record, _ in rebuild:
                for old_chunk in existing_chunks.get(record.id, []):
                    await chunks.delete(old_chunk)
            for deleted_record in existing.values():
                for old_chunk in existing_chunks.get(deleted_record.id, []):
                    await chunks.delete(old_chunk)
                await documents.delete(deleted_record)
            await self._session.flush()
            for record, parsed_chunks in rebuild:
                for parsed_chunk in parsed_chunks:
                    chunks.add(
                        KnowledgeChunkRecord(
                            client_id=client_id,
                            source_id=source.id,
                            document_id=record.id,
                            chunk_index=parsed_chunk.chunk_index,
                            heading_path=list(parsed_chunk.heading_path),
                            content=parsed_chunk.content,
                            start_line=parsed_chunk.start_line,
                            end_line=parsed_chunk.end_line,
                            content_hash=parsed_chunk.content_hash,
                        )
                    )
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
            chunks=sum(len(item[2]) for item in parsed_files),
        )
        log.info(
            "db_mutation_committed table=knowledge_documents "
            "business=knowledge_sync client_id={} source_id={} result={}",
            client_id,
            source_id,
            result,
        )
        return result
