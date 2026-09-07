"""Integration tests for the workspace WebSocket event stream."""

import asyncio
import unittest
from collections.abc import AsyncIterator
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.adapters.agent import RuntimeEvent, RuntimeEventType, RuntimeRequest
from app.api.router import api_router
from app.core.database import Base, Database
from app.repositories import AgentRepository, SessionRepository
from app.services.runtime_registry import RuntimeRegistry


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


class WorkspaceWebSocketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        asyncio.run(self._create_tables())
        registry = RuntimeRegistry()
        registry.register("native", WebSocketRuntime)
        app = FastAPI()
        app.state.database = self.database
        app.state.runtime_registry = registry
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
