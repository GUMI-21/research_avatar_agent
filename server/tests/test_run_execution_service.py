"""Tests for coordinating Runtime events with durable Run state."""

import unittest
from collections.abc import AsyncIterator
from unittest.mock import patch

from app.adapters.agent import RuntimeEvent, RuntimeEventType, RuntimeRequest
from app.core.database import Base, Database
from app.repositories import (
    AgentRepository,
    RunEventRepository,
    RunRepository,
    SessionRepository,
)
from app.services import RunExecutionService
from app.services.runtime_registry import RuntimeRegistry


class SuccessfulRuntime:
    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        yield RuntimeEvent(
            type=RuntimeEventType.ASSISTANT_DELTA,
            payload={"text": request.message},
        )
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)


class FailingRuntime:
    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        raise RuntimeError("provider unavailable")


class RunExecutionServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def _create_session(self, database_session, runtime: str) -> str:
        agent = await AgentRepository(database_session).create(
            "client-a", name=runtime, system_prompt="Help me.", runtime=runtime
        )
        conversation = await SessionRepository(database_session).create(
            "client-a", agent.id
        )
        await database_session.commit()
        return conversation.id

    async def test_success_updates_run_and_filters_events(self) -> None:
        async with self.database.session() as database_session:
            session_id = await self._create_session(database_session, "native")
            registry = RuntimeRegistry()
            registry.register("native", SuccessfulRuntime)
            service = RunExecutionService(database_session, registry)

            with (
                patch("app.repositories.run.log"),
                patch("app.repositories.run_event.log"),
                patch("app.services.run.log"),
                patch("app.services.run_event.log"),
            ):
                streamed = [
                    item
                    async for item in service.stream(
                        "client-a", session_id, "Hello"
                    )
                ]

            run = await RunRepository(database_session).get(
                "client-a", streamed[0].run_id
            )
            records = await RunEventRepository(database_session).list_events(
                "client-a", streamed[0].run_id
            )

        self.assertEqual(run.status, "completed")
        self.assertEqual([item.sequence for item in streamed], [1, None, 2])
        self.assertEqual(
            [record.event_type for record in records],
            ["run_started", "run_finished"],
        )

    async def test_runtime_error_marks_run_failed(self) -> None:
        async with self.database.session() as database_session:
            session_id = await self._create_session(database_session, "failing")
            registry = RuntimeRegistry()
            registry.register("failing", FailingRuntime)
            service = RunExecutionService(database_session, registry)
            streamed = []

            with (
                patch("app.repositories.run.log"),
                patch("app.repositories.run_event.log"),
                patch("app.services.run.log"),
                patch("app.services.run_event.log"),
                self.assertRaises(RuntimeError),
            ):
                async for item in service.stream("client-a", session_id, "Hello"):
                    streamed.append(item)

            run = await RunRepository(database_session).get(
                "client-a", streamed[0].run_id
            )

        self.assertEqual(run.status, "failed")
        self.assertEqual(streamed[-1].event.type, RuntimeEventType.RUN_FAILED)


if __name__ == "__main__":
    unittest.main()
