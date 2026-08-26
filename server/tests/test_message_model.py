"""Tests for visible conversation Message persistence."""

import unittest

from app.core.database import Base, Database
from app.models import AgentRecord, MessageRecord, SessionRecord


class MessageModelTest(unittest.IsolatedAsyncioTestCase):
    async def test_message_references_session_and_agent(self) -> None:
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
                await database_session.flush()
                message = MessageRecord(
                    client_id="client-a",
                    session_id=conversation.id,
                    agent_id=agent.id,
                    role="user",
                    content="What did I work on?",
                    sequence=1,
                )
                database_session.add(message)
                await database_session.commit()

                self.assertEqual(message.session_id, conversation.id)
                self.assertEqual(message.sequence, 1)
                self.assertIsNotNone(message.id)
        finally:
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
