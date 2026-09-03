"""Tests for the first client-scoped persistence model."""

import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.database import Base, Database
from app.models import AgentRecord


class AgentMigrationTest(unittest.TestCase):
    def test_migration_creates_and_removes_agents_table(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "agents.db"
            database_url = f"sqlite+aiosqlite:///{database_path}"
            config = Config(str(Path(__file__).parents[1] / "alembic.ini"))
            config.set_main_option("sqlalchemy.url", database_url)

            command.upgrade(config, "head")

            sync_engine = create_engine(f"sqlite:///{database_path}")
            inspector = inspect(sync_engine)
            self.assertIn(AgentRecord.__tablename__, inspector.get_table_names())
            self.assertIn("agent_knowledge_sources", inspector.get_table_names())
            self.assertIn(
                "uq_agents_client_name",
                {item["name"] for item in inspector.get_unique_constraints("agents")},
            )
            command.check(config)

            command.downgrade(config, "base")
            self.assertNotIn("agents", inspect(sync_engine).get_table_names())
            sync_engine.dispose()


class AgentModelTest(unittest.IsolatedAsyncioTestCase):
    async def test_agent_defaults_are_persisted(self) -> None:
        database = Database("sqlite+aiosqlite:///:memory:")
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            async with database.session() as session:
                agent = AgentRecord(
                    client_id="client-a",
                    name="Personal",
                    system_prompt="Help with my work.",
                )
                session.add(agent)
                await session.commit()

                self.assertEqual(agent.runtime, "native")
                self.assertEqual(agent.knowledge_source_ids, [])
                self.assertIsNotNone(agent.id)
                self.assertIsNotNone(agent.created_at)
        finally:
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
