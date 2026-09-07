"""Tests for durable Agent Run event persistence."""

import unittest

from app.core.database import Base, Database
from app.models import AgentRecord, RunEventRecord, RunRecord, SessionRecord


class RunEventModelTest(unittest.IsolatedAsyncioTestCase):
    async def test_event_preserves_normalized_payload_and_order(self) -> None:
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
                await database_session.flush()
                event = RunEventRecord(
                    client_id="client-a",
                    run_id=run.id,
                    event_type="run_started",
                    payload={"status": "running"},
                    sequence=1,
                )
                database_session.add(event)
                await database_session.commit()

                self.assertEqual(event.payload, {"status": "running"})
                self.assertEqual(event.sequence, 1)
                self.assertIsNotNone(event.id)
        finally:
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
