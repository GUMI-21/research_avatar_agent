"""Teaching WebSocket execution, shared Session guard and persisted outcomes."""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import func, select

from app.adapters.agent import NativeAgentRuntime
from app.adapters.knowledge import HashEmbeddingAdapter
from app.adapters.llm import LLMClient, LLMRequest, LLMResult
from app.api.router import api_router
from app.core.database import Base, Database
from app.models import MessageRecord, RunEventRecord, RunRecord
from app.repositories import AgentRepository, SessionRepository, TeachingRepository
from app.schemas.llm import LLMProvider
from app.services.courses import CourseCatalog
from app.services.run_execution import RunExecutionService
from app.services.runtime_registry import RuntimeRegistry
from app.services.session_run_guard import SessionRunBusyError, SessionRunGuard
from app.tools import ToolApprovalBroker


class TeachingLLM(LLMClient):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []
        self.output = json.dumps({"reply": "Which kana is i?", "avatar": {"expression": "happy"}})
        self.block = False
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.active = 0

    async def generate(self, request: LLMRequest) -> LLMResult:
        self.requests.append(request)
        self.active += 1
        self.started.set()
        try:
            if self.block:
                await self.release.wait()
            return LLMResult(self.output, LLMProvider.MOCK, "teaching-test")
        finally:
            self.active -= 1


class TeachingWebSocketTest(unittest.TestCase):
    def setUp(self) -> None:
        # 取消 SQL 时连接可能被驱动丢弃；用文件库模拟真实部署，避免内存库随连接消失。
        self.directory = tempfile.TemporaryDirectory()
        self.database = Database(f"sqlite+aiosqlite:///{Path(self.directory.name) / 'teaching.db'}")
        self.catalog = CourseCatalog((Path(__file__).resolve().parents[2] / "courses",))
        self.guard = SessionRunGuard()
        self.llm = TeachingLLM()
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
        self.session_id = self.client.portal.call(self._seed)
        self.binding_path = f"/api/v1/avatar/sessions/{self.session_id}/teaching"
        self.headers = {"X-Client-ID": "client-a"}
        self.assertEqual(self.client.put(self.binding_path, headers=self.headers, json={}).status_code, 200)

    def tearDown(self) -> None:
        self.client.portal.call(self.database.dispose)
        self.client_context.__exit__(None, None, None)
        self.directory.cleanup()

    async def _seed(self) -> str:
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with self.database.session() as session:
            agent = await AgentRepository(session).create("client-a", name="Teacher", system_prompt="Teach kindly.")
            conversation = await SessionRepository(session).create("client-a", agent.id)
            await session.commit()
            return conversation.id

    def _send(self, socket, **changes) -> None:
        socket.send_json({"type": "send_message", "session_id": self.session_id, "content": "hi", **changes})

    def _finish(self, socket) -> list[dict]:
        frames = []
        for _ in range(30):
            frame = socket.receive_json()
            frames.append(frame)
            if frame["type"] in {"run_finished", "run_failed", "run_cancelled", "error"}:
                return frames
        self.fail("Missing terminal frame")

    async def _idle(self) -> None:
        async with asyncio.timeout(3):
            while self.guard._active:
                await asyncio.sleep(0.001)

    async def _started(self) -> None:
        await asyncio.wait_for(self.llm.started.wait(), 3)

    async def _snapshot(self):
        async with self.database.session() as session:
            runs = list((await session.scalars(select(RunRecord).order_by(RunRecord.created_at))).all())
            messages = list((await session.scalars(select(MessageRecord).order_by(MessageRecord.sequence))).all())
            state = await TeachingRepository(session).get("client-a", self.session_id)
            return runs, messages, state

    def test_multi_turn_uses_course_recent_messages_and_persists_plain_reply(self) -> None:
        with self.client.websocket_connect("/api/v1/ws?client_id=client-a") as socket:
            self._send(socket)
            first = self._finish(socket)
            self.assertEqual(first[-1]["type"], "run_finished")
            self.assertEqual([frame["payload"]["text"] for frame in first if frame["type"] == "assistant_delta"], ["Which kana is i?"])
            self.assertEqual(first[-1]["payload"]["teaching"]["avatar"]["expression"], "happy")
            self.client.portal.call(self._idle)
            self._send(socket, content="い")
            self.assertEqual(self._finish(socket)[-1]["type"], "run_finished")
            self.client.portal.call(self._idle)
        self.assertEqual(len(self.llm.requests), 2)
        self.assertIn("lesson: hiragana-vowels", self.llm.requests[0].instructions)
        self.assertIn("Which kana is i?", self.llm.requests[1].message)
        self.assertEqual(self.llm.requests[0].tools, ())
        runs, messages, state = self.client.portal.call(self._snapshot)
        self.assertEqual([run.status for run in runs], ["completed", "completed"])
        self.assertEqual([message.role for message in messages], ["user", "assistant", "user", "assistant"])
        self.assertEqual(messages[1].content, "Which kana is i?")
        self.assertEqual((state.completed_turns, state.state_version), (0, 1))

    def test_second_connection_and_binding_put_are_busy_then_cancel_releases_guard(self) -> None:
        self.llm.block = True
        with self.client.websocket_connect("/api/v1/ws?client_id=client-a") as first:
            self._send(first)
            started = first.receive_json()
            self.assertEqual(started["type"], "run_started")
            self.client.portal.call(self._started)
            with self.client.websocket_connect("/api/v1/ws?client_id=client-a") as second:
                self._send(second)
                self.assertEqual(second.receive_json()["code"], "session_busy")
            self.assertEqual(self.client.put(self.binding_path, headers=self.headers, json={}).status_code, 409)
            first.send_json({"type": "cancel_run", "run_id": started["run_id"]})
            self.assertEqual(self._finish(first)[-1]["type"], "run_cancelled")
            self.client.portal.call(self._idle)
            self.assertEqual(self.llm.active, 0)
            self.llm.block = False
            self._send(first)
            self.assertEqual(self._finish(first)[-1]["type"], "run_finished")
            self.client.portal.call(self._idle)
        runs, _, _ = self.client.portal.call(self._snapshot)
        self.assertEqual([run.status for run in runs], ["cancelled", "completed"])
        self.assertEqual(len(self.llm.requests), 2)

    def test_disconnect_cancels_model_and_releases_session(self) -> None:
        self.llm.block = True
        with self.client.websocket_connect("/api/v1/ws?client_id=client-a") as socket:
            self._send(socket)
            self.assertEqual(socket.receive_json()["type"], "run_started")
            self.client.portal.call(self._started)
        self.client.portal.call(self._idle)
        self.assertEqual(self.llm.active, 0)
        runs, messages, _ = self.client.portal.call(self._snapshot)
        self.assertEqual([run.status for run in runs], ["cancelled"])
        self.assertEqual([message.role for message in messages], ["user"])

    def test_early_consumer_close_records_cancelled_before_releasing_guard(self) -> None:
        async def close_early():
            async with self.database.session() as session:
                stream = RunExecutionService(
                    session, self.app.state.runtime_registry,
                    course_catalog=self.catalog, session_run_guard=self.guard,
                ).stream("client-a", self.session_id, "hi")
                self.assertEqual((await anext(stream)).event.type.value, "run_started")
                await stream.aclose()
                self.assertEqual(self.guard._active, set())
        self.client.portal.call(close_early)
        runs, _, _ = self.client.portal.call(self._snapshot)
        self.assertEqual([run.status for run in runs], ["cancelled"])
        self.assertEqual(self.llm.requests, [])

    def test_validation_and_cross_client_fail_before_creating_run(self) -> None:
        for client_id, changes, code in (
            ("client-b", {}, "not_found"),
            ("client-a", {"target_agent_id": "missing"}, "not_found"),
        ):
            with self.subTest(client_id=client_id), self.client.websocket_connect(f"/api/v1/ws?client_id={client_id}") as socket:
                self._send(socket, **changes)
                self.assertEqual(socket.receive_json()["code"], code)
        self.app.state.course_catalog = CourseCatalog(())
        with self.client.websocket_connect("/api/v1/ws?client_id=client-a") as socket:
            self._send(socket)
            self.assertEqual(socket.receive_json()["code"], "not_found")
        self.client.portal.call(self._idle)
        runs, messages, _ = self.client.portal.call(self._snapshot)
        self.assertEqual((runs, messages, self.llm.requests), ([], [], []))

    def test_missing_shared_guard_fails_closed_for_teaching(self) -> None:
        self.app.state.session_run_guard = None
        with self.client.websocket_connect("/api/v1/ws?client_id=client-a") as socket:
            self._send(socket)
            self.assertEqual(socket.receive_json()["code"], "teaching_conflict")
        runs, messages, _ = self.client.portal.call(self._snapshot)
        self.assertEqual((runs, messages, self.llm.requests), ([], [], []))

    def test_parser_failure_has_one_failed_terminal_no_assistant_and_allows_retry(self) -> None:
        self.llm.output = '{"reply":"incomplete'
        with self.client.websocket_connect("/api/v1/ws?client_id=client-a") as socket:
            self._send(socket)
            frames = self._finish(socket)
            self.assertEqual(frames[-1]["type"], "run_failed")
            self.assertFalse(any(frame["type"] == "assistant_delta" for frame in frames))
            self.assertEqual(socket.receive_json()["code"], "run_failed")
            self.client.portal.call(self._idle)
            self.llm.output = '{"reply":"Try again."}'
            self._send(socket)
            self.assertEqual(self._finish(socket)[-1]["type"], "run_finished")
            self.client.portal.call(self._idle)
        runs, messages, _ = self.client.portal.call(self._snapshot)
        self.assertEqual([run.status for run in runs], ["failed", "completed"])
        self.assertEqual([message.role for message in messages], ["user", "user", "assistant"])
        async def terminal_count():
            async with self.database.session() as session:
                return await session.scalar(select(func.count()).select_from(RunEventRecord).where(
                    RunEventRecord.run_id == runs[0].id, RunEventRecord.event_type == "run_failed"))
        self.assertEqual(self.client.portal.call(terminal_count), 1)


class SessionRunGuardTest(unittest.IsolatedAsyncioTestCase):
    async def test_scope_busy_failure_and_cancellation_release(self) -> None:
        guard = SessionRunGuard()
        async with guard.claim("a", "s"):
            with self.assertRaises(SessionRunBusyError):
                async with guard.claim("a", "s"):
                    self.fail("Must not queue")
            async with guard.claim("b", "s"), guard.claim("a", "other"):
                pass
        with self.assertRaises(ValueError):
            async with guard.claim("a", "s"):
                raise ValueError("failure")
        with self.assertRaises(asyncio.CancelledError):
            async with guard.claim("a", "s"):
                raise asyncio.CancelledError()
        async with guard.claim("a", "s"):
            pass
        self.assertEqual(guard._active, set())
