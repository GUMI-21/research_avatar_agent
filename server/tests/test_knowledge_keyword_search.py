"""Integration tests for migration-backed Chinese keyword retrieval."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config

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
                    async with database.session() as session:
                        for client_id in ("client-a", "client-b"):
                            source = KnowledgeSourceRecord(
                                client_id=client_id,
                                name="Notes",
                                root_path=f"/{client_id}/notes",
                            )
                            session.add(source)
                            await session.flush()
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
                finally:
                    await database.dispose()

            asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
