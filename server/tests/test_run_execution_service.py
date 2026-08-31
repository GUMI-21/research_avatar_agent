"""Tests for coordinating Runtime events with durable Run state."""

import asyncio
import unittest
from collections.abc import AsyncIterator
from decimal import Decimal
from unittest.mock import patch

from app.adapters.agent import RuntimeEvent, RuntimeEventType, RuntimeRequest
from app.core.database import Base, Database
from app.repositories import (
    AgentRepository,
    MessageRepository,
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
        yield RuntimeEvent(
            type=RuntimeEventType.USAGE_UPDATED,
            payload={
                "provider": "openai",
                "model": "gpt-5.6-luna",
                "input_tokens": 12_000,
                "output_tokens": 3_000,
                "cache_read_tokens": 4_000,
                "cache_write_tokens": 1_000,
            },
        )
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)


class FailingRuntime:
    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        raise RuntimeError("provider unavailable")


class BlockingRuntime:
    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        await asyncio.Event().wait()


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
                patch("app.repositories.message.log"),
                patch("app.repositories.run_event.log"),
                patch("app.services.message.log"),
                patch("app.services.run.log"),
                patch("app.services.run_event.log"),
                patch(
                    "app.services.run_execution.perf_counter",
                    side_effect=[10.0, 10.125, 10.5],
                ),
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
            messages = await MessageRepository(database_session).list_messages(
                "client-a", session_id
            )

        self.assertEqual(run.status, "completed")
        self.assertEqual([item.sequence for item in streamed], [1, None, 2, 3])
        self.assertEqual(
            [record.event_type for record in records],
            ["run_started", "usage_updated", "run_finished"],
        )
        self.assertEqual(run.provider, "openai")
        self.assertEqual(run.model, "gpt-5.6-luna")
        self.assertEqual(run.input_tokens, 12_000)
        self.assertEqual(run.output_tokens, 3_000)
        self.assertEqual(run.cache_read_tokens, 4_000)
        self.assertEqual(run.cache_write_tokens, 1_000)
        self.assertEqual(run.cost_usd, Decimal("0.005330"))
        self.assertEqual(run.cost_status, "estimated")
        self.assertEqual(run.duration_ms, 500)
        self.assertEqual(run.time_to_first_token_ms, 125)
        self.assertEqual(streamed[2].event.payload["cost_usd"], "0.005330")
        self.assertEqual(streamed[-1].event.payload["duration_ms"], 500)
        self.assertEqual(
            streamed[-1].event.payload["time_to_first_token_ms"], 125
        )
        self.assertEqual([item.role for item in messages], ["user", "assistant"])
        self.assertEqual([item.content for item in messages], ["Hello", "Hello"])
        self.assertTrue(all(item.run_id == run.id for item in messages))

    async def test_runtime_error_marks_run_failed(self) -> None:
        async with self.database.session() as database_session:
            session_id = await self._create_session(database_session, "failing")
            registry = RuntimeRegistry()
            registry.register("failing", FailingRuntime)
            service = RunExecutionService(database_session, registry)
            streamed = []

            with (
                patch("app.repositories.run.log"),
                patch("app.repositories.message.log"),
                patch("app.repositories.run_event.log"),
                patch("app.services.message.log"),
                patch("app.services.run.log"),
                patch("app.services.run_event.log"),
                self.assertRaises(RuntimeError),
            ):
                async for item in service.stream("client-a", session_id, "Hello"):
                    streamed.append(item)

            run = await RunRepository(database_session).get(
                "client-a", streamed[0].run_id
            )
            messages = await MessageRepository(database_session).list_messages(
                "client-a", session_id
            )

        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error_type, "RuntimeError")
        self.assertIsNotNone(run.duration_ms)
        self.assertEqual(streamed[-1].event.type, RuntimeEventType.RUN_FAILED)
        self.assertEqual([item.role for item in messages], ["user"])

    async def test_task_cancellation_marks_run_cancelled(self) -> None:
        async with self.database.session() as database_session:
            session_id = await self._create_session(database_session, "blocking")
            registry = RuntimeRegistry()
            registry.register("blocking", BlockingRuntime)
            stream = RunExecutionService(database_session, registry).stream(
                "client-a", session_id, "Hello"
            )
            with (
                patch("app.repositories.run.log"),
                patch("app.repositories.message.log"),
                patch("app.repositories.run_event.log"),
                patch("app.services.message.log"),
                patch("app.services.run.log"),
                patch("app.services.run_event.log"),
            ):
                started = await anext(stream)
                waiting = asyncio.create_task(anext(stream))
                await asyncio.sleep(0)
                waiting.cancel()
                cancelled = await waiting
                with self.assertRaises(asyncio.CancelledError):
                    await anext(stream)

            run = await RunRepository(database_session).get(
                "client-a", started.run_id
            )
            events = await RunEventRepository(database_session).list_events(
                "client-a", started.run_id
            )

        self.assertEqual(run.status, "cancelled")
        self.assertIsNotNone(run.duration_ms)
        self.assertEqual(cancelled.event.type, RuntimeEventType.RUN_CANCELLED)
        self.assertEqual(events[-1].event_type, "run_cancelled")


if __name__ == "__main__":
    unittest.main()
