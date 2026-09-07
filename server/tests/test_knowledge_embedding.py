"""Tests for the replaceable knowledge embedding boundary."""

import unittest
from datetime import datetime, timezone
from math import isclose

from app.adapters.knowledge import HashEmbeddingAdapter
from app.core.database import Base, Database
from app.models import (
    KnowledgeChunkEmbeddingRecord,
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
)


class KnowledgeEmbeddingTest(unittest.IsolatedAsyncioTestCase):
    async def test_hash_adapter_is_deterministic_and_normalized(self) -> None:
        adapter = HashEmbeddingAdapter(dimensions=12)
        query = await adapter.embed_query("个人知识库")
        documents = await adapter.embed_documents(["个人知识库", "Agent"])

        self.assertEqual(query, documents[0])
        self.assertEqual(len(query), 12)
        self.assertTrue(isclose(sum(value * value for value in query), 1.0))

    async def test_embedding_record_is_persisted_with_chunk(self) -> None:
        database = Database("sqlite+aiosqlite:///:memory:")
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                source = KnowledgeSourceRecord(
                    client_id="client-a", name="Notes", root_path="/vault"
                )
                session.add(source)
                await session.flush()
                document = KnowledgeDocumentRecord(
                    client_id="client-a",
                    source_id=source.id,
                    relative_path="agent.md",
                    title="Agent",
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
                    heading_path=[],
                    content="Agent memory",
                    start_line=1,
                    end_line=1,
                    content_hash="b" * 64,
                )
                session.add(chunk)
                await session.flush()
                record = KnowledgeChunkEmbeddingRecord(
                    client_id="client-a",
                    source_id=source.id,
                    chunk_id=chunk.id,
                    provider="local",
                    model="hash-test-v1",
                    dimensions=2,
                    vector=[0.6, 0.8],
                    content_hash=chunk.content_hash,
                )
                session.add(record)
                await session.commit()

                self.assertEqual(record.vector, [0.6, 0.8])
                self.assertEqual(record.chunk_id, chunk.id)
        finally:
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
