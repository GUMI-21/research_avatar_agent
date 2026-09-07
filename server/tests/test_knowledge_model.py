"""Tests for the first Obsidian RAG persistence records."""

import unittest
from datetime import datetime, timezone

from app.core.database import Base, Database
from app.models import (
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
)


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
                await session.flush()
                chunk = KnowledgeChunkRecord(
                    client_id="client-a",
                    source_id=source.id,
                    document_id=document.id,
                    chunk_index=0,
                    heading_path=["RAG", "Retrieval"],
                    content="Hybrid retrieval combines two channels.",
                    start_line=10,
                    end_line=12,
                    content_hash="b" * 64,
                )
                session.add(chunk)
                await session.commit()

                self.assertEqual(source.source_type, "obsidian")
                self.assertEqual(source.sync_status, "pending")
                self.assertEqual(document.frontmatter, {})
                self.assertEqual(document.source_id, source.id)
                self.assertEqual(chunk.heading_path, ["RAG", "Retrieval"])
                self.assertEqual((chunk.start_line, chunk.end_line), (10, 12))
        finally:
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
