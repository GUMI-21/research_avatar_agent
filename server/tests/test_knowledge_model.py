"""Tests for the first Obsidian RAG persistence records."""

import unittest
from datetime import datetime, timezone

from app.core.database import Base, Database
from app.models import KnowledgeDocumentRecord, KnowledgeSourceRecord


class KnowledgeModelTest(unittest.IsolatedAsyncioTestCase):
    async def test_source_and_document_defaults_are_persisted(self) -> None:
        database = Database("sqlite+aiosqlite:///:memory:")
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                source = KnowledgeSourceRecord(
                    client_id="client-a",
                    name="Personal Notes",
                    root_path="/vault",
                )
                session.add(source)
                await session.flush()
                document = KnowledgeDocumentRecord(
                    client_id="client-a",
                    source_id=source.id,
                    relative_path="RAG/overview.md",
                    title="RAG Overview",
                    content_hash="a" * 64,
                    source_modified_at=datetime.now(timezone.utc),
                )
                session.add(document)
                await session.commit()

                self.assertEqual(source.source_type, "obsidian")
                self.assertEqual(source.sync_status, "pending")
                self.assertEqual(document.frontmatter, {})
                self.assertEqual(document.source_id, source.id)
        finally:
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
