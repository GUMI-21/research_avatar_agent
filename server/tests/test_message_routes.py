"""Tests for paginated conversation Message history routes."""

import unittest

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.database import Base, Database
from app.repositories import MessageRepository


class MessageRoutesTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        app = FastAPI()
        app.state.database = self.database
        app.include_router(api_router)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        await self.database.dispose()

    async def test_history_uses_cursor_and_client_scope(self) -> None:
        headers = {"X-Client-ID": "client-a"}
        agent = await self.client.post(
            "/api/v1/agents",
            headers=headers,
            json={"name": "Personal", "system_prompt": "Help me."},
        )
        agent_id = agent.json()["id"]
        conversation = await self.client.post(
            "/api/v1/sessions",
            headers=headers,
            json={"agent_id": agent_id},
        )
        session_id = conversation.json()["id"]
        async with self.database.session() as database_session:
            messages = MessageRepository(database_session)
            for content in ("one", "two", "three"):
                await messages.append(
                    "client-a",
                    session_id,
                    agent_id,
                    role="user",
                    content=content,
                )
            await database_session.commit()

        latest = await self.client.get(
            f"/api/v1/sessions/{session_id}/messages?limit=2",
            headers=headers,
        )
        older = await self.client.get(
            f"/api/v1/sessions/{session_id}/messages?before_sequence=2&limit=2",
            headers=headers,
        )
        concealed = await self.client.get(
            f"/api/v1/sessions/{session_id}/messages",
            headers={"X-Client-ID": "client-b"},
        )

        self.assertEqual(
            [item["sequence"] for item in latest.json()["messages"]], [2, 3]
        )
        self.assertTrue(latest.json()["has_more"])
        self.assertEqual(latest.json()["next_cursor"], 2)
        self.assertEqual(
            [item["sequence"] for item in older.json()["messages"]], [1]
        )
        self.assertFalse(older.json()["has_more"])
        self.assertEqual(concealed.status_code, 404)


if __name__ == "__main__":
    unittest.main()
