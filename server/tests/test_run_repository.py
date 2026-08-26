"""Tests for client-scoped Agent Run operations."""

import unittest
from unittest.mock import patch

from app.core.database import Base, Database
from app.repositories import (
    AgentRepository,
    RunParentNotFoundError,
    RunRepository,
    SessionRepository,
)


class RunRepositoryTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_run_state_and_parents_are_client_scoped(self) -> None:
        async with self.database.session() as database_session:
            agents = AgentRepository(database_session)
            personal = await agents.create(
                "client-a", name="Personal", system_prompt="Help client A."
            )
            outsider = await agents.create(
                "client-b", name="Personal", system_prompt="Help client B."
            )
            conversation = await SessionRepository(database_session).create(
                "client-a", personal.id
            )
            runs = RunRepository(database_session)
            with patch("app.repositories.run.log") as mocked_log:
                run = await runs.create(
                    "client-a",
                    conversation.id,
                    personal.id,
                    runtime="native",
                )
                running = await runs.set_status("client-a", run.id, "running")
                failed = await runs.set_status(
                    "client-a",
                    run.id,
                    "failed",
                    error_type="RuntimeError",
                    error_message="provider unavailable",
                )
                self.assertEqual(mocked_log.info.call_count, 3)
            await database_session.commit()

            hidden = await runs.get("client-b", run.id)
            with self.assertRaises(RunParentNotFoundError):
                await runs.create(
                    "client-a",
                    conversation.id,
                    outsider.id,
                    runtime="native",
                )

        self.assertEqual(running, run)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.error_type, "RuntimeError")
        self.assertIsNotNone(failed.started_at)
        self.assertIsNotNone(failed.completed_at)
        self.assertIsNone(hidden)


if __name__ == "__main__":
    unittest.main()
