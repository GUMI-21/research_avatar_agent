"""Tests for Agent Run lifecycle and transaction boundaries."""

import unittest
from unittest.mock import patch

from app.core.database import Base, Database
from app.repositories import AgentRepository, SessionRepository
from app.services import InvalidRunTransitionError, RunNotFoundError, RunService


class RunServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_run_lifecycle_commits_and_rejects_invalid_transition(self) -> None:
        async with self.database.session() as database_session:
            agent = await AgentRepository(database_session).create(
                "client-a", name="Personal", system_prompt="Help me."
            )
            conversation = await SessionRepository(database_session).create(
                "client-a", agent.id
            )
            await database_session.commit()
            service = RunService(database_session)

            with (
                patch("app.repositories.run.log"),
                patch("app.services.run.log") as service_log,
            ):
                run = await service.create_run(
                    "client-a",
                    conversation.id,
                    agent.id,
                    runtime="native",
                )
                await service.transition("client-a", run.id, "running")
                completed = await service.transition(
                    "client-a", run.id, "completed"
                )
                self.assertEqual(service_log.info.call_count, 3)

            with self.assertRaises(InvalidRunTransitionError):
                await service.transition("client-a", run.id, "running")
            with self.assertRaises(RunNotFoundError):
                await service.transition("client-b", run.id, "failed")

        self.assertEqual(completed.status, "completed")
        self.assertIsNotNone(completed.started_at)
        self.assertIsNotNone(completed.completed_at)


if __name__ == "__main__":
    unittest.main()
