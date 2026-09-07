"""Tests for incremental knowledge embedding indexing."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.adapters.knowledge import HashEmbeddingAdapter
from app.core.database import Base, Database
from app.models import KnowledgeChunkRecord, KnowledgeDocumentRecord, KnowledgeSourceRecord
from app.repositories import KnowledgeEmbeddingRepository
from app.services import KnowledgeEmbeddingService, KnowledgeSourceNotFoundError


class KnowledgeEmbeddingServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_index_is_incremental_and_client_scoped(self) -> None:
        async with self.database.session() as session:
            source = KnowledgeSourceRecord(
                client_id="client-a", name="Notes", root_path="/vault"
            )
            session.add(source)
            await session.flush()
            document = KnowledgeDocumentRecord(
                client_id="client-a",
                source_id=source.id,
                relative_path="rag.md",
                title="RAG",
                content_hash="a" * 64,
                source_modified_at=datetime.now(timezone.utc),
            )
            session.add(document)
            await session.flush()
            chunks = [
                KnowledgeChunkRecord(
                    client_id="client-a",
                    source_id=source.id,
                    document_id=document.id,
                    chunk_index=index,
                    heading_path=[],
                    content=content,
                    start_line=index + 1,
                    end_line=index + 1,
                    content_hash=content_hash * 64,
                )
                for index, (content, content_hash) in enumerate(
                    [("Agent memory", "b"), ("Hybrid retrieval", "c")]
                )
            ]
            session.add_all(chunks)
            await session.commit()

            service = KnowledgeEmbeddingService(session, HashEmbeddingAdapter(6))
            with patch("app.services.knowledge_embedding.log"):
                first = await service.index_source("client-a", source.id, batch_size=1)
                second = await service.index_source("client-a", source.id)
            chunks[0].content = "Updated memory"
            chunks[0].content_hash = "d" * 64
            with patch("app.services.knowledge_embedding.log"):
                third = await service.index_source("client-a", source.id)
            records = await KnowledgeEmbeddingRepository(session).list_for_model(
                "client-a", source.id, "local", "hash-test-v1"
            )

            self.assertEqual((first.indexed, first.unchanged), (2, 0))
            self.assertEqual((second.indexed, second.unchanged), (0, 2))
            self.assertEqual((third.indexed, third.unchanged), (1, 1))
            self.assertEqual(len(records), 2)
            self.assertTrue(all(record.dimensions == 6 for record in records))
            with self.assertRaises(KnowledgeSourceNotFoundError):
                await service.index_source("client-b", source.id)


if __name__ == "__main__":
    unittest.main()
