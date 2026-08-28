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
    def test_send_message_streams_normalized_events(self, *_mocks) -> None:
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

        self.assertEqual(
            [frame["type"] for frame in frames],
            ["run_started", "assistant_delta", "run_finished"],
        )
        self.assertEqual([frame["sequence"] for frame in frames], [1, None, 2])
        self.assertEqual(len({frame["run_id"] for frame in frames}), 1)

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
