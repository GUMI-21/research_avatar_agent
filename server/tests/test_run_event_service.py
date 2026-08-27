"""Tests for Runtime event visibility and persistence policy."""

import unittest
from unittest.mock import patch

from app.adapters.agent import RuntimeEvent, RuntimeEventType
from app.core.database import Base, Database
from app.repositories import (
    AgentRepository,
    RunEventRepository,
    RunRepository,
    SessionRepository,
)
from app.services import RunEventService, UnsupportedRuntimeEventError


class RunEventServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def test_policy_persists_only_public_durable_events(self) -> None:
        async with self.database.session() as database_session:
            agent = await AgentRepository(database_session).create(
                "client-a", name="Personal", system_prompt="Help me."
            )
            conversation = await SessionRepository(database_session).create(
                "client-a", agent.id
            )
            run = await RunRepository(database_session).create(
                "client-a", conversation.id, agent.id, runtime="native"
            )
            await database_session.commit()
            service = RunEventService(database_session)

            with (
                patch("app.repositories.run_event.log"),
                patch("app.services.run_event.log") as service_log,
            ):
                saved = await service.process(
                    "client-a",
                    run.id,
                    RuntimeEvent(type=RuntimeEventType.RUN_STARTED),
                )
                delta = await service.process(
                    "client-a",
                    run.id,
                    RuntimeEvent(
                        type=RuntimeEventType.ASSISTANT_DELTA,
                        payload={"text": "partial"},
                    ),
                )
                retry = await service.process(
                    "client-a",
                    run.id,
                    RuntimeEvent(type=RuntimeEventType.PROVIDER_RETRY),
                )
                self.assertEqual(service_log.info.call_count, 2)

            records = await RunEventRepository(database_session).list_events(
                "client-a", run.id
            )

        self.assertEqual(saved.sequence, 1)
        self.assertIsNone(delta)
        self.assertIsNone(retry)
        self.assertEqual([record.event_type for record in records], ["run_started"])

    async def test_unknown_event_is_rejected(self) -> None:
        event = RuntimeEvent(type="unknown")  # type: ignore[arg-type]
        with self.assertRaises(UnsupportedRuntimeEventError):
            RunEventService.policy_for(event)


if __name__ == "__main__":
    unittest.main()
