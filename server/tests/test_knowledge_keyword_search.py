"""Integration tests for migration-backed Chinese keyword retrieval."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from alembic import command
from alembic.config import Config
from fastapi import FastAPI

from app.api.router import api_router
from app.core.database import Database
from app.models import (
    KnowledgeChunkRecord,
    KnowledgeDocumentRecord,
    KnowledgeSourceRecord,
)
from app.repositories import KnowledgeChunkRepository


class KnowledgeKeywordSearchTest(unittest.TestCase):
    def test_fts_ranks_chinese_and_scopes_clients(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "search.db"
            database_url = f"sqlite+aiosqlite:///{database_path}"
            config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)
            command.upgrade(config, "head")

            async def scenario() -> None:
                database = Database(database_url)
                try:
                    source_ids: dict[str, str] = {}
                    async with database.session() as session:
                        for client_id in ("client-a", "client-b"):
                            source = KnowledgeSourceRecord(
                                client_id=client_id,
                                name="Notes",
                                root_path=f"/{client_id}/notes",
                            )
                            session.add(source)
                            await session.flush()
                            source_ids[client_id] = source.id
                            document = KnowledgeDocumentRecord(
                                client_id=client_id,
                                source_id=source.id,
                                relative_path="RAG.md",
                                title="RAG",
                                content_hash="a" * 64,
                                source_modified_at=source.created_at,
                            )
                            session.add(document)
                            await session.flush()
                            session.add(
                                KnowledgeChunkRecord(
                                    client_id=client_id,
                                    source_id=source.id,
                                    document_id=document.id,
                                    chunk_index=0,
                                    heading_path=["检索"],
                                    content="混合检索结合关键词检索与向量检索。",
                                    start_line=3,
                                    end_line=3,
                                    content_hash="b" * 64,
                                )
                            )
                        await session.commit()
                        repository = KnowledgeChunkRepository(session)
                        hits = await repository.search_keyword(
                            "client-a", "如何实现混合检索"
                        )
                        short_hits = await repository.search_keyword(
                            "client-a", "检索"
                        )
                        blank_hits = await repository.search_keyword("client-a", "  ")

                    self.assertEqual(len(hits), 1)
                    self.assertEqual(hits[0].relative_path, "RAG.md")
                    self.assertEqual(hits[0].heading_path, ("检索",))
                    self.assertGreater(hits[0].score, 0)
                    self.assertEqual(len(short_hits), 1)
                    self.assertEqual(blank_hits, [])

                    app = FastAPI()
                    app.state.database = database
                    app.include_router(api_router)
                    async with httpx.AsyncClient(
                        transport=httpx.ASGITransport(app=app),
                        base_url="http://testserver",
                    ) as client:
                        with patch("app.services.knowledge_retrieval.log"):
                            response = await client.post(
                                f"/api/v1/knowledge/sources/"
                                f"{source_ids['client-a']}/search",
                                headers={"X-Client-ID": "client-a"},
                                json={"query": "如何实现混合检索", "limit": 5},
                            )
                            concealed = await client.post(
                                f"/api/v1/knowledge/sources/"
                                f"{source_ids['client-a']}/search",
                                headers={"X-Client-ID": "client-b"},
                                json={"query": "混合检索"},
                            )

                    self.assertEqual(response.status_code, 200)
                    citation = response.json()["citations"][0]
                    self.assertEqual(citation["relative_path"], "RAG.md")
                    self.assertEqual(citation["start_line"], 3)
                    self.assertEqual(citation["retrieval_method"], "keyword")
                    self.assertIn("混合检索", citation["snippet"])
                    self.assertEqual(concealed.status_code, 404)
                finally:
                    await database.dispose()

            asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
