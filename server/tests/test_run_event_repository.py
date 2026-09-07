"""Tests for ordered and client-scoped Run Event persistence."""

import unittest
from unittest.mock import patch

from app.adapters.agent import RuntimeEvent, RuntimeEventType
from app.core.database import Base, Database
from app.repositories import (
    AgentRepository,
    RunEventRepository,
    RunEventRunNotFoundError,
    RunRepository,
    SessionRepository,
)


class RunEventRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_append_replay_and_client_scope(self) -> None:
        async with self.database.session() as database_session:
            agent = await AgentRepository(database_session).create(
                "client-a", name="Personal", system_prompt="Help client A."
            )
            conversation = await SessionRepository(database_session).create(
                "client-a", agent.id
            )
            run = await RunRepository(database_session).create(
                "client-a", conversation.id, agent.id, runtime="native"
            )
            events = RunEventRepository(database_session)
            with patch("app.repositories.run_event.log") as mocked_log:
                started = await events.append(
                    "client-a",
                    run.id,
                    RuntimeEvent(type=RuntimeEventType.RUN_STARTED),
                )
                tool = await events.append(
                    "client-a",
                    run.id,
                    RuntimeEvent(
                        type=RuntimeEventType.TOOL_STARTED,
                        payload={"tool_name": "search_notes"},
                    ),
                )
                self.assertEqual(mocked_log.info.call_count, 2)
            await database_session.commit()

            replay = await events.list_events(
                "client-a", run.id, after_sequence=1
            )
            hidden = await events.list_events("client-b", run.id)
            with self.assertRaises(RunEventRunNotFoundError):
                await events.append(
                    "client-b",
                    run.id,
                    RuntimeEvent(type=RuntimeEventType.RUN_FINISHED),
                )

        self.assertEqual(started.sequence, 1)
        self.assertEqual(tool.sequence, 2)
        self.assertEqual([event.event_type for event in replay], ["tool_started"])
        self.assertEqual(hidden, [])


if __name__ == "__main__":
    unittest.main()
