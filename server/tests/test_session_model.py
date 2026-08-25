"""Tests for client-scoped conversation Session persistence."""

import unittest

from app.core.database import Base, Database
from app.models import AgentRecord, SessionRecord


class SessionModelTest(unittest.IsolatedAsyncioTestCase):
    async def test_session_references_agent_and_has_defaults(self) -> None:
        database = Database("sqlite+aiosqlite:///:memory:")
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            async with database.session() as database_session:
                agent = AgentRecord(
                    client_id="client-a",
                    name="Personal",
                    system_prompt="Help with my work.",
                )
                database_session.add(agent)
                await database_session.flush()
                conversation = SessionRecord(
                    client_id="client-a",
                    agent_id=agent.id,
                )
                database_session.add(conversation)
                await database_session.commit()

                self.assertEqual(conversation.title, "New conversation")
                self.assertEqual(conversation.agent_id, agent.id)
                self.assertIsNotNone(conversation.id)
        finally:
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
