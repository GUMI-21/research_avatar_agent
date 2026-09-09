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
    KnowledgeSourceRepository,
    KnowledgeChunkHit,
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


class ContextRuntime:
    request: RuntimeRequest | None = None

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        type(self).request = request
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        yield RuntimeEvent(type=RuntimeEventType.ASSISTANT_DELTA, payload={"text": "ok"})
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)


class StubRetrieval:
    def __init__(self, hits_by_source: dict[str, list[KnowledgeChunkHit]]) -> None:
        self.hits_by_source = hits_by_source
        self.calls: list[tuple[str, str, int]] = []

    async def search_keyword(
        self, client_id: str, source_id: str, query: str, *, limit: int
    ) -> list[KnowledgeChunkHit]:
        self.calls.append((client_id, source_id, limit))
        return self.hits_by_source.get(source_id, [])


class FailingRetrieval:
    async def search_keyword(self, *args: object, **kwargs: object) -> list[KnowledgeChunkHit]:
        raise RuntimeError("retrieval unavailable")


class BlockingRetrieval:
    def __init__(self) -> None:
        self.started = asyncio.Event()
        self.released = asyncio.Event()

    async def search_keyword(self, *args: object, **kwargs: object) -> list[KnowledgeChunkHit]:
        self.started.set()
        await self.released.wait()
        return []


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

    async def _create_bound_session(
        self, database_session, *, runtime: str = "native"
    ) -> tuple[str, str, str]:
        sources = KnowledgeSourceRepository(database_session)
        first = await sources.create(
            "client-a", name="first", root_path="/tmp/first", source_type="markdown"
        )
        second = await sources.create(
            "client-a", name="second", root_path="/tmp/second", source_type="markdown"
        )
        _ = await sources.create(
            "client-b", name="foreign", root_path="/tmp/foreign", source_type="markdown"
        )
        agent = await AgentRepository(database_session).create(
            "client-a",
            name="with-knowledge",
            system_prompt="Help me.",
            runtime=runtime,
            knowledge_sources=[second, first],
        )
        conversation = await SessionRepository(database_session).create(
            "client-a", agent.id
        )
        await database_session.commit()
        return conversation.id, first.id, second.id

    @staticmethod
    def _hit(chunk_id: str, content: str) -> KnowledgeChunkHit:
        return KnowledgeChunkHit(
            chunk_id=chunk_id,
            document_id=f"doc-{chunk_id}",
            title="Note",
            relative_path=f"{chunk_id}.md",
            heading_path=("知识",),
            content=content,
            start_line=1,
            end_line=2,
            score=1.0,
        )

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

    async def test_bound_sources_reach_native_request_with_scoped_budget(self) -> None:
        ContextRuntime.request = None
        async with self.database.session() as database_session:
            session_id, first_id, second_id = await self._create_bound_session(
                database_session
            )
            retrieval = StubRetrieval(
                {
                    first_id: [self._hit("first-1", "A" * 2000)],
                    second_id: [self._hit("second-1", "B" * 2000)],
                }
            )
            registry = RuntimeRegistry()
            registry.register("native", ContextRuntime)
            service = RunExecutionService(database_session, registry)
            service._retrieval = retrieval
            streamed = [
                item
                async for item in service.stream(
                    "client-a", session_id, "检索问题"
                )
            ]

        request = ContextRuntime.request
        self.assertIsNotNone(request)
        assert request is not None
        self.assertLessEqual(len(request.knowledge_context), 6000)
        self.assertIn("first-1.md", request.knowledge_context)
        self.assertIn("second-1.md", request.knowledge_context)
        self.assertEqual(
            [source_id for _, source_id, _ in retrieval.calls],
            sorted((first_id, second_id)),
        )
        self.assertTrue(all(client_id == "client-a" for client_id, _, _ in retrieval.calls))
        self.assertTrue(all(limit == 5 for _, _, limit in retrieval.calls))
        self.assertEqual(streamed[-1].event.type, RuntimeEventType.RUN_FINISHED)

    async def test_retrieval_failure_marks_run_failed(self) -> None:
        ContextRuntime.request = None
        async with self.database.session() as database_session:
            session_id, _, _ = await self._create_bound_session(database_session)
            registry = RuntimeRegistry()
            registry.register("native", ContextRuntime)
            service = RunExecutionService(database_session, registry)
            service._retrieval = FailingRetrieval()
            streamed = []
            with self.assertRaises(RuntimeError):
                async for item in service.stream("client-a", session_id, "检索问题"):
                    streamed.append(item)
            run = await RunRepository(database_session).get(
                "client-a", streamed[0].run_id
            )

        self.assertEqual(run.status, "failed")
        self.assertEqual(run.error_type, "RuntimeError")
        self.assertFalse(ContextRuntime.request is not None)

    async def test_non_native_runtime_skips_retrieval_and_keeps_request_unchanged(self) -> None:
        ContextRuntime.request = None
        async with self.database.session() as database_session:
            session_id, first_id, second_id = await self._create_bound_session(
                database_session, runtime="custom_worker"
            )
            retrieval = FailingRetrieval()
            registry = RuntimeRegistry()
            registry.register("custom_worker", ContextRuntime)
            service = RunExecutionService(database_session, registry)
            service._retrieval = retrieval
            streamed = [
                item
                async for item in service.stream(
                    "client-a", session_id, "原始问题"
                )
            ]

        self.assertEqual(streamed[-1].event.type, RuntimeEventType.RUN_FINISHED)
        self.assertIsNotNone(ContextRuntime.request)
        assert ContextRuntime.request is not None
        self.assertEqual(ContextRuntime.request.message, "原始问题")
        self.assertEqual(ContextRuntime.request.knowledge_context, "")
        self.assertFalse(any(
            item.event.type is RuntimeEventType.CONTEXT_PREPARED for item in streamed
        ))

    async def test_cancel_after_context_prepared_does_not_claim_model_use(self) -> None:
        ContextRuntime.request = None
        async with self.database.session() as database_session:
            session_id, _, _ = await self._create_bound_session(database_session)
            registry = RuntimeRegistry()
            registry.register("native", ContextRuntime)
            service = RunExecutionService(database_session, registry)
            service._retrieval = StubRetrieval({})
            stream = service.stream("client-a", session_id, "问题")
            async for item in stream:
                if item.event.type is RuntimeEventType.CONTEXT_PREPARED:
                    prepared = item
                    break
            self.assertIsNone(ContextRuntime.request)
            cancelled = await stream.athrow(asyncio.CancelledError())
            self.assertEqual(cancelled.event.type, RuntimeEventType.RUN_CANCELLED)
            with self.assertRaises(asyncio.CancelledError):
                await anext(stream)
            run = await RunRepository(database_session).get("client-a", prepared.run_id)
            self.assertEqual(run.status, "cancelled")
            self.assertIsNone(ContextRuntime.request)

    async def test_cancellation_during_retrieval_does_not_call_runtime(self) -> None:
        ContextRuntime.request = None
        async with self.database.session() as database_session:
            session_id, _, _ = await self._create_bound_session(database_session)
            retrieval = BlockingRetrieval()
            registry = RuntimeRegistry()
            registry.register("native", ContextRuntime)
            service = RunExecutionService(database_session, registry)
            service._retrieval = retrieval
            stream = service.stream("client-a", session_id, "检索问题")
            started = await anext(stream)
            retrieval_started = await anext(stream)
            self.assertEqual(
                retrieval_started.event.type, RuntimeEventType.RETRIEVAL_STARTED
            )
            waiting = asyncio.create_task(anext(stream))
            await retrieval.started.wait()
            waiting.cancel()
            cancelled = await waiting
            with self.assertRaises(asyncio.CancelledError):
                await anext(stream)
            run = await RunRepository(database_session).get(
                "client-a", started.run_id
            )

        self.assertEqual(cancelled.event.type, RuntimeEventType.RUN_CANCELLED)
        self.assertEqual(run.status, "cancelled")
        self.assertIsNone(ContextRuntime.request)


if __name__ == "__main__":
    unittest.main()
