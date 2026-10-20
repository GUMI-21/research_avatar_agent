"""Internal teaching request preparation and enforced Native/graph restrictions."""

import unittest
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy import func, select

from app.adapters.agent import HandoffTarget, NativeAgentRuntime, RuntimeEvent, RuntimeEventType, RuntimeRequest
from app.adapters.llm import LLMClient, LLMRequest, LLMResult, LLMStreamChunk, LLMToolCall
from app.core.database import Base, Database
from app.models import MessageRecord, RunRecord
from app.orchestration import AgentRunTarget, LangGraphRunOrchestrator
from app.orchestration.run_graph import HandoffRoutingError
from app.repositories import AgentRepository, SessionRepository, TeachingRepository, TeachingSessionNotFoundError
from app.schemas.llm import LLMProvider
from app.schemas.teaching import CourseSelection
from app.services.courses import CourseCatalog, CourseSelectionNotFoundError
from app.services.teaching import TeachingBindingConflictError, TeachingService
from app.tools import ToolApprovalBroker, ToolRegistry


class TeachingLLM(LLMClient):
    def __init__(self, tool_call: LLMToolCall | None = None) -> None:
        self.requests: list[LLMRequest] = []
        self.tool_call = tool_call

    async def generate(self, request: LLMRequest) -> LLMResult:
        raise AssertionError("Expected the streaming boundary")

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)
        yield LLMStreamChunk(
            text="" if self.tool_call else '{"schema_version":1,"reply":"Which kana is i?"}',
            provider=LLMProvider.MOCK, model="teaching-test", tool_call=self.tool_call,
        )


class HandoffRuntime:
    async def stream(self, request: RuntimeRequest) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(type=RuntimeEventType.HANDOFF_REQUESTED, payload={
            "to_agent_id": "other", "task_summary": "do work",
        })


class TeachingContextTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.catalog = CourseCatalog((Path(__file__).resolve().parents[2] / "courses",))
        async with self.database.session() as session:
            agent = await AgentRepository(session).create(
                "client-a", name="Teacher", system_prompt="Help the learner.",
            )
            conversation = await SessionRepository(session).create("client-a", agent.id)
            await session.commit()
            self.request = RuntimeRequest(
                "run-test", "client-a", agent.id, conversation.id, "hi",
                system_prompt=agent.system_prompt,
                conversation_context="assistant: Which kana is i?",
                memory_context="Learner prefers short examples.", memory_ids=("memory-1",),
                knowledge_context="Reference: い = i.",
                handoff_targets=(HandoffTarget("other", "Coder"),),
            )
            await TeachingService(session, self.catalog).bind("client-a", conversation.id, CourseSelection())

    async def asyncTearDown(self) -> None:
        await self.database.dispose()

    async def _prepare(self, request: RuntimeRequest | None = None) -> RuntimeRequest:
        async with self.database.session() as session:
            return await TeachingService(session, self.catalog).prepare(request or self.request)

    async def test_preparation_preserves_context_and_does_not_mutate_database(self) -> None:
        prepared = await self._prepare()
        course = self.catalog.get("gojuon-en")
        self.assertEqual(prepared.mode, "teaching")
        self.assertEqual(prepared.handoff_targets, ())
        self.assertTrue(prepared.system_prompt.startswith(self.request.system_prompt))
        self.assertIn(course.instructions, prepared.system_prompt)
        self.assertIn(course.version_hash, prepared.system_prompt)
        self.assertIn("lesson: hiragana-vowels", prepared.system_prompt)
        self.assertIn("state_version: 1", prepared.system_prompt)
        self.assertIn("committed_turns: 0 (not a mastery score)", prepared.system_prompt)
        self.assertIn("Return only one JSON object", prepared.system_prompt)
        for field in ("run_id", "client_id", "session_id", "agent_id", "message",
                      "conversation_context", "memory_context", "memory_ids", "knowledge_context"):
            self.assertEqual(getattr(prepared, field), getattr(self.request, field))
        self.assertEqual(self.request.mode, "workspace")
        self.assertEqual(len(self.request.handoff_targets), 1)
        async with self.database.session() as session:
            state = await TeachingRepository(session).get("client-a", self.request.session_id)
            self.assertEqual((state.completed_turns, state.state_version), (0, 1))
            for model in (RunRecord, MessageRecord):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model)), 0)

    async def test_missing_and_cross_client_bindings_are_rejected(self) -> None:
        for request in (
            replace(self.request, client_id="client-b"),
            replace(self.request, session_id="missing"),
        ):
            with self.subTest(request=request):
                with self.assertRaises(TeachingSessionNotFoundError):
                    await self._prepare(request)

    async def test_agent_changes_and_manual_target_override_are_rejected(self) -> None:
        with self.assertRaises(TeachingBindingConflictError):
            await self._prepare(replace(self.request, agent_id="other"))
        async with self.database.session() as session:
            agent = await AgentRepository(session).get("client-a", self.request.agent_id)
            agent.runtime = "codex"
            await session.commit()
        with self.assertRaisesRegex(TeachingBindingConflictError, "bound Native Agent"):
            await self._prepare()

    async def test_removed_or_changed_script_cannot_be_prepared(self) -> None:
        async with self.database.session() as session:
            with self.assertRaises(CourseSelectionNotFoundError):
                await TeachingService(session, CourseCatalog(())).prepare(self.request)
            changed = Mock(spec=CourseCatalog)
            changed.resolve.return_value = replace(self.catalog.get("gojuon-en"), version_hash="b" * 64)
            with self.assertRaisesRegex(TeachingBindingConflictError, "script has changed"):
                await TeachingService(session, changed).prepare(self.request)

    async def test_course_budget_rejects_instead_of_truncating(self) -> None:
        prepared = await self._prepare()
        size = len(prepared.system_prompt) - len(self.request.system_prompt) - 2
        with patch("app.services.teaching.TEACHING_CONTEXT_BUDGET_CHARS", size):
            self.assertEqual(await self._prepare(), prepared)
        with patch("app.services.teaching.TEACHING_CONTEXT_BUDGET_CHARS", size - 1):
            with self.assertRaisesRegex(TeachingBindingConflictError, "context budget"):
                await self._prepare()

    async def test_native_keeps_teaching_instructions_on_greeting_and_offers_no_tools(self) -> None:
        request = await self._prepare()
        client = TeachingLLM()
        tools = Mock(spec=ToolRegistry)
        runtime = NativeAgentRuntime(client, tools)
        events = [event async for event in runtime.stream(request)]
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FINISHED)
        self.assertEqual(client.requests[0].tools, ())
        self.assertIn(request.system_prompt, client.requests[0].instructions)
        self.assertNotIn("only a greeting", client.requests[0].instructions)
        self.assertIn(request.conversation_context, client.requests[0].message)
        self.assertIn(request.memory_context, client.requests[0].message)
        self.assertIn(request.knowledge_context, client.requests[0].message)
        tools.definitions.assert_not_called()

    async def test_unsolicited_tools_and_delegation_are_rejected_before_side_effects(self) -> None:
        for call in (LLMToolCall("file_write", {"path": "private", "content": "write"}),
                     LLMToolCall("delegate_to_agent", {"target_agent_id": "other", "task_summary": "work"})):
            with self.subTest(tool=call.name):
                client = TeachingLLM(call)
                tools = Mock(spec=ToolRegistry)
                tools.execute = AsyncMock()
                approvals = Mock(spec=ToolApprovalBroker)
                runtime = NativeAgentRuntime(client, tools, approvals)
                events = []
                request = replace(await self._prepare(), handoff_targets=self.request.handoff_targets)
                with self.assertRaisesRegex(RuntimeError, "tools were disabled"):
                    async for event in runtime.stream(request):
                        events.append(event)
                self.assertEqual(client.requests[0].tools, ())
                self.assertEqual(events[-1].type, RuntimeEventType.RUN_FAILED)
                self.assertFalse(any(event.type in {
                    RuntimeEventType.TOOL_STARTED, RuntimeEventType.APPROVAL_REQUIRED,
                    RuntimeEventType.HANDOFF_REQUESTED, RuntimeEventType.RUN_FINISHED,
                } for event in events))
                tools.execute.assert_not_awaited()
                approvals.create.assert_not_called()

    async def test_graph_rejects_manual_and_runtime_requested_handoffs(self) -> None:
        request = await self._prepare()
        target_runtime = Mock()
        orchestrator = LangGraphRunOrchestrator(HandoffRuntime(), handoff_targets={
            "other": AgentRunTarget(target_runtime, replace(self.request, agent_id="other")),
        })
        with self.assertRaisesRegex(HandoffRoutingError, "forbids Agent handoff"):
            _ = [event async for event in orchestrator.stream(request, entry_agent_id="other")]
        events = []
        with self.assertRaisesRegex(HandoffRoutingError, "forbids Agent handoff"):
            async for event in orchestrator.stream(request):
                events.append(event)
        self.assertFalse(any(event.type in {
            RuntimeEventType.HANDOFF_REQUESTED, RuntimeEventType.HANDOFF_STARTED,
            RuntimeEventType.HANDOFF_FINISHED,
        } for event in events))
        target_runtime.stream.assert_not_called()
