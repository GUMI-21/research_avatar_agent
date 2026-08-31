"""Tests for knowledge source path validation and client isolation."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.database import Base, Database
from app.repositories import KnowledgeSourceRepository
from app.services import (
    KnowledgeSourceConflictError,
    KnowledgeSourcePathError,
    KnowledgeSourceService,
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


if __name__ == "__main__":
    unittest.main()
