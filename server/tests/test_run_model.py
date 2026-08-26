"""Tests for Agent Run summary persistence."""

import unittest

from app.core.database import Base, Database
from app.models import AgentRecord, RunRecord, SessionRecord


class RunModelTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_preserves_execution_defaults(self) -> None:
        database = Database("sqlite+aiosqlite:///:memory:")
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as database_session:
                agent = AgentRecord(
                    client_id="client-a", name="Personal", system_prompt="Help me."
                )
                database_session.add(agent)
                await database_session.flush()
                conversation = SessionRecord(client_id="client-a", agent_id=agent.id)
                database_session.add(conversation)
                await database_session.flush()
                run = RunRecord(
                    client_id="client-a",
                    session_id=conversation.id,
                    agent_id=agent.id,
                    runtime="native",
                )
                database_session.add(run)
                await database_session.commit()

                self.assertEqual(run.status, "pending")
                self.assertEqual(run.cost_status, "unavailable")
                self.assertIsNotNone(run.id)
        finally:
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
