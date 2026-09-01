"""Tests for knowledge source path validation and client isolation."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.database import Base, Database
from app.repositories import KnowledgeDocumentRepository, KnowledgeSourceRepository
from app.services import (
    KnowledgeSourceConflictError,
    KnowledgeSourceNotFoundError,
    KnowledgeSourcePathError,
    KnowledgeSourceService,
    KnowledgeSourceSyncError,
)


class KnowledgeSourceServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_create_normalizes_path_and_scopes_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "notes"
            root.mkdir()
            async with self.database.session() as session:
                service = KnowledgeSourceService(session)
                with patch("app.services.knowledge.log"):
                    source = await service.create(
                        "client-a",
                        name="Notes",
                        root_path=str(root / ".." / "notes"),
                    )
                visible = await KnowledgeSourceRepository(session).list_sources(
                    "client-a"
                )
                hidden = await KnowledgeSourceRepository(session).list_sources(
                    "client-b"
                )

            self.assertEqual(source.root_path, str(root.resolve()))
            self.assertEqual([item.id for item in visible], [source.id])
            self.assertEqual(hidden, [])

    async def test_duplicate_root_and_missing_directory_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            async with self.database.session() as session:
                service = KnowledgeSourceService(session)
                with patch("app.services.knowledge.log"):
                    await service.create(
                        "client-a",
                        name="Notes",
                        root_path=temp_dir,
                    )
                with self.assertRaises(KnowledgeSourceConflictError):
                    await service.create(
                        "client-a",
                        name="Same directory",
                        root_path=temp_dir,
                    )
                with self.assertRaises(KnowledgeSourcePathError):
                    await service.create(
                        "client-a",
                        name="Missing",
                        root_path=str(Path(temp_dir) / "missing"),
                    )
                with self.assertRaises(KnowledgeSourcePathError):
                    await service.create(
                        "client-a",
                        name="Filesystem root",
                        root_path=Path(temp_dir).anchor,
                    )

    async def test_sync_creates_updates_and_deletes_document_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "first.md").write_text("# First", encoding="utf-8")
            (root / "old.md").write_text("old", encoding="utf-8")
            async with self.database.session() as session:
                service = KnowledgeSourceService(session)
                with patch("app.services.knowledge.log"):
                    source = await service.create(
                        "client-a", name="Notes", root_path=temp_dir
                    )
                    first_result = await service.sync("client-a", source.id)
                self.assertEqual((first_result.created, first_result.scanned), (2, 2))

                (root / "first.md").write_text("# Changed", encoding="utf-8")
                (root / "old.md").unlink()
                (root / "new.md").write_text("# New", encoding="utf-8")
                with patch("app.services.knowledge.log"):
                    second_result = await service.sync("client-a", source.id)
                records = await KnowledgeDocumentRepository(session).list_for_source(
                    "client-a", source.id
                )

            self.assertEqual(second_result.created, 1)
            self.assertEqual(second_result.updated, 1)
            self.assertEqual(second_result.deleted, 1)
            self.assertEqual(
                sorted((record.relative_path, record.title) for record in records),
                [("first.md", "Changed"), ("new.md", "New")],
            )
            self.assertEqual(source.sync_status, "ready")
            self.assertIsNotNone(source.last_synced_at)

    async def test_sync_failure_is_recorded_and_client_is_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "invalid.md").write_text(
                "---\ntags: [broken\n---\nbody", encoding="utf-8"
            )
            async with self.database.session() as session:
                service = KnowledgeSourceService(session)
                with patch("app.services.knowledge.log"):
                    source = await service.create(
                        "client-a", name="Notes", root_path=temp_dir
                    )
                    with self.assertRaises(KnowledgeSourceSyncError):
                        await service.sync("client-a", source.id)
                self.assertEqual(source.sync_status, "failed")
                with self.assertRaises(KnowledgeSourceNotFoundError):
                    await service.sync("client-b", source.id)


if __name__ == "__main__":
    unittest.main()
