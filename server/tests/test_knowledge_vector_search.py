"""Tests for exact vector retrieval over persisted JSON vectors."""

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from app.adapters.knowledge import HashEmbeddingAdapter
from app.api.router import api_router
from app.core.database import Base, Database
from app.models import (
    KnowledgeChunkEmbeddingRecord,
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
)


class QueryEmbeddingAdapter(HashEmbeddingAdapter):
    provider = "test"
    model = "fixed-v1"

    def __init__(self) -> None:
        super().__init__(2)

    async def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


class KnowledgeVectorSearchTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.embedding = QueryEmbeddingAdapter()

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_vector_search_ranks_current_embeddings(self) -> None:
        async with self.database.session() as session:
            source = KnowledgeSourceRecord(
                client_id="client-a", name="Notes", root_path="/notes"
            )
            session.add(source)
            await session.flush()
            document = KnowledgeDocumentRecord(
                client_id="client-a",
                source_id=source.id,
                relative_path="RAG.md",
                title="RAG",
                content_hash="a" * 64,
                source_modified_at=datetime.now(timezone.utc),
            )
            session.add(document)
            await session.flush()
            for index, (content, vector) in enumerate(
                (("最相关", [1.0, 0.0]), ("较不相关", [0.0, 1.0]))
            ):
                content_hash = str(index + 1) * 64
                chunk = KnowledgeChunkRecord(
                    client_id="client-a",
                    source_id=source.id,
                    document_id=document.id,
                    chunk_index=index,
                    heading_path=["检索"],
                    content=content,
                    start_line=index + 1,
                    end_line=index + 1,
                    content_hash=content_hash,
                )
                session.add(chunk)
                await session.flush()
                session.add(
                    KnowledgeChunkEmbeddingRecord(
                        client_id="client-a",
                        source_id=source.id,
                        chunk_id=chunk.id,
                        provider="test",
                        model="fixed-v1",
                        dimensions=2,
                        vector=vector,
                        content_hash=content_hash,
                    )
                )
            await session.commit()

        app = FastAPI()
        app.state.database = self.database
        app.state.embedding_client = self.embedding
        app.include_router(api_router)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            with patch("app.services.knowledge_retrieval.log"):
                response = await client.post(
                    f"/api/v1/knowledge/sources/{source.id}/search",
                    headers={"X-Client-ID": "client-a"},
                    json={"query": "相关内容", "strategy": "vector"},
                )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["strategy"], "vector")
        self.assertEqual(
            [item["snippet"] for item in body["citations"]],
            ["最相关", "较不相关"],
        )
        self.assertEqual(body["citations"][0]["retrieval_method"], "vector")


if __name__ == "__main__":
    unittest.main()
