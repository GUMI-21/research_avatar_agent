"""Integration tests for the workspace WebSocket event stream."""

import asyncio
import unittest
from collections.abc import AsyncIterator
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver

from app.adapters.agent import (
    NativeAgentRuntime,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeRequest,
)
from app.adapters.llm import LLMClient, LLMRequest, LLMResult
from app.adapters.knowledge import HashEmbeddingAdapter
from app.api.router import api_router
from app.core.database import Base, Database
from app.repositories import AgentRepository, KnowledgeSourceRepository, SessionRepository
from app.schemas.llm import LLMProvider
from app.services.runtime_registry import RuntimeRegistry
from app.tools import ToolApprovalBroker


class WebSocketRuntime:
    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        await asyncio.sleep(0.05)
        yield RuntimeEvent(
            type=RuntimeEventType.ASSISTANT_DELTA,
            payload={"text": f"Reply: {request.message}"},
        )
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)


class ApprovalRuntime:
    def __init__(self, approvals: ToolApprovalBroker) -> None:
        self.approvals = approvals

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        pending = self.approvals.create(request.client_id, request.run_id)
        yield RuntimeEvent(
            type=RuntimeEventType.APPROVAL_REQUIRED,
            payload={"approval_id": pending.id, "tool_name": "write_markdown"},
        )
        approved = await pending.decision
        yield RuntimeEvent(
            type=RuntimeEventType.TOOL_FINISHED,
            payload={"tool_name": "write_markdown", "approved": approved},
        )
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)

class RecordingLLMClient(LLMClient):
    def __init__(self) -> None:
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResult:
        self.requests.append(request)
        return LLMResult("answer", LLMProvider.MOCK, "mock-echo")


class BlockingRetrieval:
    async def search_keyword(
        self, *args: object, **kwargs: object
    ) -> list[object]:
        await asyncio.Event().wait()
        return []

    async def search_hybrid(
        self, *args: object, **kwargs: object
    ) -> list[object]:
        await asyncio.Event().wait()
        return []


class WorkspaceWebSocketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        asyncio.run(self._create_tables())
        registry = RuntimeRegistry()
        registry.register("native", WebSocketRuntime)
        self.registry = registry
        app = FastAPI()
        app.state.database = self.database
        app.state.runtime_registry = registry
        app.state.embedding_client = HashEmbeddingAdapter()
        app.state.graph_checkpointer = InMemorySaver()
        self.approvals = ToolApprovalBroker()
        app.state.tool_approval_broker = self.approvals
        app.include_router(api_router)
        self.client = TestClient(app)
        self.session_id = asyncio.run(self._create_session())

    def tearDown(self) -> None:
        self.client.close()
        asyncio.run(self.database.dispose())

    async def _create_tables(self) -> None:
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def _create_session(self) -> str:
        async with self.database.session() as database_session:
            agent = await AgentRepository(database_session).create(
                "client-a", name="Personal", system_prompt="Help me."
            )
            conversation = await SessionRepository(database_session).create(
                "client-a", agent.id
            )
            await database_session.commit()
            return conversation.id

    async def _create_bound_session(self) -> str:
        async with self.database.session() as database_session:
            source = await KnowledgeSourceRepository(database_session).create(
                "client-a",
                name="Notes",
                root_path="C:/temporary-notes",
                source_type="markdown",
            )
            agent = await AgentRepository(database_session).create(
                "client-a",
                name="RAG",
                system_prompt="Use notes.",
                runtime="native",
                knowledge_sources=[source],
            )
            conversation = await SessionRepository(database_session).create(
                "client-a", agent.id
            )
            await database_session.commit()
            return conversation.id

    async def _create_target_agent(self) -> str:
        async with self.database.session() as database_session:
            agent = await AgentRepository(database_session).create(
                "client-a", name="Target", system_prompt="Handle delegated work."
            )
            await database_session.commit()
            return agent.id

    @patch("app.api.routes.workspace_ws.log")
    @patch("app.repositories.message.log")
    @patch("app.repositories.run.log")
    @patch("app.repositories.run_event.log")
    @patch("app.services.message.log")
    @patch("app.services.run.log")
    @patch("app.services.run_event.log")
    def test_send_message_streams_and_replays_durable_events(self, *_mocks) -> None:
        with self.client.websocket_connect(
            "/api/v1/ws?client_id=client-a"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "send_message",
                    "session_id": self.session_id,
                    "content": "Hello",
                }
            )
            frames = [websocket.receive_json() for _ in range(3)]

        run_id = frames[0]["run_id"]
        with self.client.websocket_connect(
            "/api/v1/ws?client_id=client-a"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "resume_run",
                    "run_id": run_id,
                    "after_sequence": 1,
                }
            )
            replayed = [websocket.receive_json() for _ in range(2)]
        with self.client.websocket_connect(
            "/api/v1/ws?client_id=client-b"
        ) as websocket:
            websocket.send_json(
                {"type": "resume_run", "run_id": run_id, "after_sequence": 0}
            )
            hidden = websocket.receive_json()

        self.assertEqual(
            [frame["type"] for frame in frames],
            ["run_started", "assistant_delta", "run_finished"],
        )
        self.assertEqual([frame["sequence"] for frame in frames], [1, None, 2])
        self.assertEqual(len({frame["run_id"] for frame in frames}), 1)
        self.assertEqual(
            [frame["type"] for frame in replayed],
            ["run_finished", "replay_complete"],
        )
        self.assertEqual(replayed[-1]["last_sequence"], 2)
        self.assertEqual(replayed[-1]["count"], 1)
        self.assertFalse(replayed[-1]["has_more"])
        self.assertEqual(hidden["type"], "replay_complete")
        self.assertEqual(hidden["count"], 0)

    @patch("app.api.routes.workspace_ws.log")
    @patch("app.repositories.message.log")
    @patch("app.repositories.run.log")
    @patch("app.repositories.run_event.log")
    @patch("app.services.message.log")
    @patch("app.services.run.log")
    @patch("app.services.run_event.log")
    def test_send_message_can_handoff_to_target_agent(self, *_mocks) -> None:
        target_agent_id = asyncio.run(self._create_target_agent())
        with self.client.websocket_connect(
            "/api/v1/ws?client_id=client-a"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "send_message",
                    "session_id": self.session_id,
                    "content": "Delegate this",
                    "target_agent_id": target_agent_id,
                }
            )
            frames = [websocket.receive_json() for _ in range(5)]

        self.assertEqual(
            [frame["type"] for frame in frames],
            [
                "run_started",
                "handoff_started",
                "handoff_finished",
                "assistant_delta",
                "run_finished",
            ],
        )
        self.assertEqual(frames[1]["payload"]["to_agent_id"], target_agent_id)

    @patch("app.api.routes.workspace_ws.log")
    def test_tool_approval_resumes_active_run(self, _mocked_log) -> None:
        self.registry._factories["native"] = lambda: ApprovalRuntime(self.approvals)
        with self.client.websocket_connect(
            "/api/v1/ws?client_id=client-a"
        ) as websocket:
            websocket.send_json({
                "type": "send_message",
                "session_id": self.session_id,
                "content": "Write",
            })
            started = websocket.receive_json()
            approval = websocket.receive_json()
            websocket.send_json({
                "type": "tool_approval",
                "run_id": started["run_id"],
                "approval_id": approval["payload"]["approval_id"],
                "approved": True,
            })
            finished = websocket.receive_json()
            completed = websocket.receive_json()

        self.assertEqual(approval["type"], "approval_required")
        self.assertTrue(finished["payload"]["approved"])
        self.assertEqual(completed["type"], "run_finished")
    @patch("app.api.routes.workspace_ws.log")
    def test_invalid_command_returns_safe_error(self, _mocked_log) -> None:
        with self.client.websocket_connect(
            "/api/v1/ws?client_id=client-a"
        ) as websocket:
            websocket.send_json({"type": "unknown"})
            frame = websocket.receive_json()

        self.assertEqual(frame["type"], "error")
        self.assertEqual(frame["code"], "invalid_command")

    @patch("app.api.routes.workspace_ws.log")
    @patch("app.repositories.message.log")
    @patch("app.repositories.run.log")
    @patch("app.repositories.run_event.log")
    @patch("app.services.message.log")
    @patch("app.services.run.log")
    @patch("app.services.run_event.log")
    def test_ping_is_handled_while_run_is_active(self, *_mocks) -> None:
        with self.client.websocket_connect(
            "/api/v1/ws?client_id=client-a"
        ) as websocket:
            command = {
                "type": "send_message",
                "session_id": self.session_id,
                "content": "Hello",
            }
            websocket.send_json(command)
            started = websocket.receive_json()
            websocket.send_json({"type": "ping", "request_id": "ping-1"})
            pong = websocket.receive_json()
            websocket.send_json(command)
            rejected = websocket.receive_json()
            remaining = [websocket.receive_json() for _ in range(2)]

        self.assertEqual(started["type"], "run_started")
        self.assertEqual(pong, {"type": "pong", "request_id": "ping-1"})
        self.assertEqual(rejected["code"], "run_in_progress")
        self.assertEqual(
            [frame["type"] for frame in remaining],
            ["assistant_delta", "run_finished"],
        )

    @patch("app.api.routes.workspace_ws.log")
    @patch("app.repositories.message.log")
    @patch("app.repositories.run.log")
    @patch("app.repositories.run_event.log")
    @patch("app.services.message.log")
    @patch("app.services.run.log")
    @patch("app.services.run_event.log")
    def test_active_run_can_be_cancelled(self, *_mocks) -> None:
        with self.client.websocket_connect(
            "/api/v1/ws?client_id=client-a"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "send_message",
                    "session_id": self.session_id,
                    "content": "Hello",
                }
            )
            started = websocket.receive_json()
            command = {"type": "cancel_run", "run_id": started["run_id"]}
            websocket.send_json(command)
            cancelled = websocket.receive_json()
            websocket.send_json(command)
            rejected = websocket.receive_json()

        self.assertEqual(cancelled["type"], "run_cancelled")
        self.assertEqual(cancelled["sequence"], 2)
        self.assertEqual(rejected["code"], "run_not_active")

    @patch("app.services.run_execution.KnowledgeRetrievalService")
    @patch("app.api.routes.workspace_ws.log")
    @patch("app.repositories.message.log")
    @patch("app.repositories.run.log")
    @patch("app.repositories.run_event.log")
    @patch("app.services.message.log")
    @patch("app.services.run.log")
    @patch("app.services.run_event.log")
    def test_cancel_during_retrieval_prevents_native_llm_call(
        self, *_mocks
    ) -> None:
        llm = RecordingLLMClient()
        self.registry._factories["native"] = lambda: NativeAgentRuntime(llm)
        session_id = asyncio.run(self._create_bound_session())
        with patch(
            "app.services.run_execution.KnowledgeRetrievalService",
            return_value=BlockingRetrieval(),
        ):
            with self.client.websocket_connect(
                "/api/v1/ws?client_id=client-a"
            ) as websocket:
                websocket.send_json(
                    {
                        "type": "send_message",
                        "session_id": session_id,
                        "content": "检索问题",
                    }
                )
                started = websocket.receive_json()
                retrieval_started = websocket.receive_json()
                websocket.send_json(
                    {"type": "cancel_run", "run_id": started["run_id"]}
                )
                cancelled = websocket.receive_json()

        self.assertEqual(started["type"], "run_started")
        self.assertEqual(retrieval_started["type"], "retrieval_started")
        self.assertEqual(cancelled["type"], "run_cancelled")
        self.assertEqual(llm.requests, [])

    @patch("app.api.routes.workspace_ws.log")
    def test_session_is_hidden_from_other_client(self, _mocked_log) -> None:
        with self.client.websocket_connect(
            "/api/v1/ws?client_id=client-b"
        ) as websocket:
            websocket.send_json(
                {
                    "type": "send_message",
                    "session_id": self.session_id,
                    "content": "Hello",
                }
            )
            frame = websocket.receive_json()

        self.assertEqual(frame["type"], "error")
        self.assertEqual(frame["code"], "not_found")


if __name__ == "__main__":
    unittest.main()
