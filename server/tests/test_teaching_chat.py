"""HTTP teaching reuses WebSocket execution, persistence and Session ownership."""

import asyncio
import json
import tempfile
import unittest
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import select

from app.adapters.agent import NativeAgentRuntime
from app.adapters.knowledge import HashEmbeddingAdapter
from app.adapters.llm import LLMClient, LLMRequest, LLMResult, LLMStreamChunk, LLMUsage
from app.adapters.llm.errors import LLMConfigurationError, LLMProviderError, LLMTimeoutError
from app.api.router import api_router
from app.core.database import Base, Database
from app.models import MessageRecord, RunRecord
from app.repositories import AgentRepository, SessionRepository, TeachingRepository
from app.schemas.avatar import AvatarControl
from app.schemas.llm import LLMProvider
from app.services.courses import CourseCatalog
from app.services.runtime_registry import RuntimeRegistry
from app.services.session_run_guard import SessionRunGuard
from app.tools import ToolApprovalBroker


class HTTPTeachingLLM(LLMClient):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []
        self.output = json.dumps({"reply": "Which kana is i?", "avatar": {"expression": "happy"}})
        self.error: Exception | None = None
        self.block = False
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def generate(self, request: LLMRequest) -> LLMResult:
        raise AssertionError("Do not make a second LLM call")

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)
        self.started.set()
        if self.block:
            await self.release.wait()
        if self.error:
            raise self.error
        yield LLMStreamChunk(self.output, LLMProvider.MOCK, "teaching-test")
        yield LLMStreamChunk("", LLMProvider.MOCK, "teaching-test", usage=LLMUsage(12, 4))


class TeachingChatHTTPTest(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.database = Database(f"sqlite+aiosqlite:///{Path(self.directory.name) / 'teaching.db'}")
        self.catalog = CourseCatalog((Path(__file__).resolve().parents[2] / "courses",))
        self.guard = SessionRunGuard()
        self.llm = HTTPTeachingLLM()
        self.app = FastAPI()
        registry = RuntimeRegistry()
        registry.register("native", lambda: NativeAgentRuntime(self.llm))
        self.app.state.database = self.database
        self.app.state.runtime_registry = registry
        self.app.state.embedding_client = HashEmbeddingAdapter()
        self.app.state.graph_checkpointer = InMemorySaver()
        self.app.state.tool_approval_broker = ToolApprovalBroker()
        self.app.state.course_catalog = self.catalog
        self.app.state.session_run_guard = self.guard
        self.app.include_router(api_router)
        self.client_context = TestClient(self.app)
        self.client = self.client_context.__enter__()
        self.session_id, self.unbound_id = self.client.portal.call(self._seed)
        self.headers = {"X-Client-ID": "client-a"}
        self.binding_path = f"/api/v1/avatar/sessions/{self.session_id}/teaching"
        self.assertEqual(self.client.put(self.binding_path, headers=self.headers, json={}).status_code, 200)

    def tearDown(self) -> None:
        self.client.portal.call(self.llm.release.set)
        self.client.portal.call(self.database.dispose)
        self.client_context.__exit__(None, None, None)
        self.directory.cleanup()

    async def _seed(self) -> tuple[str, str]:
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with self.database.session() as session:
            agent = await AgentRepository(session).create("client-a", name="Teacher", system_prompt="Teach kindly.")
            conversations = SessionRepository(session)
            bound = await conversations.create("client-a", agent.id)
            unbound = await conversations.create("client-a", agent.id)
            await session.commit()
            return bound.id, unbound.id

    def _post(self, message="hi", **kwargs):
        return self.client.post("/api/v1/avatar/chat", headers=self.headers,
                                json={"session_id": self.session_id, "message": message}, **kwargs)

    async def _async_post(self):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://testserver") as client:
            return await client.post("/api/v1/avatar/chat", headers=self.headers,
                                     json={"session_id": self.session_id, "message": "hi"})

    async def _started(self) -> None:
        await asyncio.wait_for(self.llm.started.wait(), 3)

    async def _idle(self) -> None:
        async with asyncio.timeout(3):
            while self.guard._active:
                await asyncio.sleep(0.001)

    async def _snapshot(self):
        async with self.database.session() as session:
            runs = list((await session.scalars(select(RunRecord).order_by(RunRecord.created_at))).all())
            messages = list((await session.scalars(select(MessageRecord).order_by(MessageRecord.sequence))).all())
            state = await TeachingRepository(session).get("client-a", self.session_id)
            return runs, messages, state

    def test_success_and_multi_turn_return_plain_reply_and_persist_usage(self) -> None:
        response = self._post(" hi ")
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(set(result), {"schema_version", "reply", "avatar", "session_id", "run_id", "fallback_reason"})
        self.assertEqual(result["reply"], "Which kana is i?")
        self.assertEqual(result["avatar"]["expression"], "happy")
        self.assertIsNone(result["fallback_reason"])
        self.assertEqual(self._post("い").status_code, 200)
        self.assertEqual(len(self.llm.requests), 2)
        self.assertIn("lesson: hiragana-vowels", self.llm.requests[0].instructions)
        self.assertIn("Which kana is i?", self.llm.requests[1].message)
        self.assertEqual(self.llm.requests[0].tools, ())
        runs, messages, state = self.client.portal.call(self._snapshot)
        self.assertEqual(runs[0].id, result["run_id"])
        self.assertEqual([run.status for run in runs], ["completed", "completed"])
        self.assertEqual((runs[0].input_tokens, runs[0].output_tokens), (12, 4))
        self.assertEqual([message.content for message in messages], ["hi", "Which kana is i?", "い", "Which kana is i?"])
        self.assertEqual((state.completed_turns, state.state_version), (0, 1))
        usage = self.client.get("/api/v1/usage/runs", headers=self.headers).json()["runs"]
        self.assertIn(result["run_id"], [item["id"] for item in usage])

    def test_invalid_avatar_falls_back_without_a_second_request(self) -> None:
        self.llm.output = '{"reply":"Try again.","avatar":{"action":"execute_script"}}'
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["reply"], "Try again.")
        self.assertEqual(response.json()["avatar"], AvatarControl().model_dump(mode="json"))
        self.assertEqual(response.json()["fallback_reason"], "invalid_avatar")
        self.assertEqual(len(self.llm.requests), 1)

    def test_unbound_missing_and_cross_client_sessions_fail_without_side_effects(self) -> None:
        for session_id, client_id in ((self.unbound_id, "client-a"), ("missing", "client-a"), (self.session_id, "client-b")):
            with self.subTest(session_id=session_id, client_id=client_id):
                response = self.client.post("/api/v1/avatar/chat", headers={"X-Client-ID": client_id},
                                            json={"session_id": session_id, "message": "hi"})
                self.assertEqual(response.status_code, 404)
        runs, messages, _ = self.client.portal.call(self._snapshot)
        self.assertEqual((runs, messages, self.llm.requests), ([], [], []))

    def test_headers_and_input_reject_blank_extra_or_oversized_fields(self) -> None:
        for headers in ({}, {"X-Client-ID": " "}):
            self.assertEqual(self.client.post("/api/v1/avatar/chat", headers=headers,
                                             json={"session_id": self.session_id, "message": "hi"}).status_code, 422)
        for change in ({"message": " "}, {"message": "x" * 10_001}, {"session_id": " "},
                       {"session_id": "x" * 37}, {"mode": "workspace"}, {"target_agent_id": "other"},
                       {"client_id": "client-b"}, {"course_id": "other"}):
            with self.subTest(change=change):
                payload = {"session_id": self.session_id, "message": "hi", **change}
                self.assertEqual(self.client.post("/api/v1/avatar/chat", headers=self.headers, json=payload).status_code, 422)
        self.assertEqual(self.llm.requests, [])

    def test_missing_dependencies_and_unavailable_runtime_fail_before_run(self) -> None:
        for name in ("course_catalog", "session_run_guard", "runtime_registry"):
            previous = getattr(self.app.state, name)
            setattr(self.app.state, name, None)
            self.assertEqual(self._post().status_code, 503)
            setattr(self.app.state, name, previous)
        self.app.state.runtime_registry = RuntimeRegistry()
        self.assertEqual(self._post().status_code, 503)
        runs, messages, _ = self.client.portal.call(self._snapshot)
        self.assertEqual((runs, messages, self.llm.requests), ([], [], []))

    def test_http_blocks_second_http_ws_and_binding_until_complete(self) -> None:
        self.llm.block = True
        future = self.client.portal.start_task_soon(self._async_post)
        try:
            self.client.portal.call(self._started)
            self.assertEqual(self._post().status_code, 409)
            self.assertEqual(self.client.put(self.binding_path, headers=self.headers, json={}).status_code, 409)
            with self.client.websocket_connect("/api/v1/ws?client_id=client-a") as socket:
                socket.send_json({"type": "send_message", "session_id": self.session_id, "content": "hi"})
                self.assertEqual(socket.receive_json()["code"], "session_busy")
        finally:
            self.client.portal.call(self.llm.release.set)
        self.assertEqual(future.result(timeout=3).status_code, 200)
        self.assertEqual(len(self.llm.requests), 1)
        self.assertEqual(self.guard._active, set())

    def test_ws_blocks_http_and_cancellation_allows_http_retry(self) -> None:
        self.llm.block = True
        with self.client.websocket_connect("/api/v1/ws?client_id=client-a") as socket:
            socket.send_json({"type": "send_message", "session_id": self.session_id, "content": "hi"})
            started = socket.receive_json()
            self.client.portal.call(self._started)
            self.assertEqual(self._post().status_code, 409)
            socket.send_json({"type": "cancel_run", "run_id": started["run_id"]})
            for _ in range(10):
                if socket.receive_json()["type"] == "run_cancelled":
                    break
            else:
                self.fail("Missing cancellation terminal")
            self.client.portal.call(self._idle)
        self.llm.block = False
        self.assertEqual(self._post().status_code, 200)
        runs, _, _ = self.client.portal.call(self._snapshot)
        self.assertEqual([run.status for run in runs], ["cancelled", "completed"])

    def test_bad_output_returns_sanitized_502_and_retains_usage_then_allows_retry(self) -> None:
        self.llm.output = '{"reply":"private-incomplete'
        response = self._post()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private-incomplete", response.text)
        runs, messages, _ = self.client.portal.call(self._snapshot)
        self.assertEqual(runs[0].status, "failed")
        self.assertEqual(runs[0].input_tokens, 12)
        self.assertEqual([message.role for message in messages], ["user"])
        self.llm.output = '{"reply":"Try again."}'
        self.assertEqual(self._post().status_code, 200)
        self.assertEqual(self.guard._active, set())

    def test_provider_errors_have_stable_statuses_and_do_not_leak_details(self) -> None:
        for error, status in ((LLMConfigurationError("private-config-details"), 400),
                              (LLMTimeoutError(LLMProvider.OPENAI), 504),
                              (LLMProviderError(LLMProvider.OPENAI, "private-provider-details"), 502),
                              (RuntimeError("private-internal-details"), 500)):
            with self.subTest(error=type(error).__name__):
                self.llm.error = error
                response = self._post()
                self.assertEqual(response.status_code, status)
                self.assertNotIn("private-", response.text)
                self.assertEqual(self.guard._active, set())

    def test_invalid_runtime_completion_cannot_return_fake_success(self) -> None:
        from app.adapters.agent import RuntimeEvent, RuntimeEventType
        from app.services.run_execution import RunExecutionService, StreamedRunEvent
        async def incomplete(*args, **kwargs):
            yield StreamedRunEvent("run-test", RuntimeEvent(RuntimeEventType.ASSISTANT_DELTA, {"text": "partial"}), None)
        with patch.object(RunExecutionService, "stream", incomplete):
            response = self._post()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("partial", response.text)
        async def missing_presentation_fields(*args, **kwargs):
            yield StreamedRunEvent("run-test", RuntimeEvent(RuntimeEventType.ASSISTANT_DELTA, {"text": "partial"}), None)
            yield StreamedRunEvent("run-test", RuntimeEvent(RuntimeEventType.RUN_FINISHED, {"teaching": {}}), 1)
        with patch.object(RunExecutionService, "stream", missing_presentation_fields):
            response = self._post()
        self.assertEqual(response.status_code, 502)
