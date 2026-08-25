"""Tests for client-scoped conversation Session HTTP routes."""

import unittest

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.database import Base, Database


class SessionRoutesTest(unittest.IsolatedAsyncioTestCase):
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

    async def test_session_resources_are_scoped_by_client(self) -> None:
        agent = await self.client.post(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-a"},
            json={"name": "Personal", "system_prompt": "Help me."},
        )
        payload = {"agent_id": agent.json()["id"], "title": "Project"}
        created = await self.client.post(
            "/api/v1/sessions",
            headers={"X-Client-ID": "client-a"},
            json=payload,
        )
        session_id = created.json()["id"]
        visible = await self.client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"X-Client-ID": "client-a"},
        )
        visible_list = await self.client.get(
            "/api/v1/sessions",
            headers={"X-Client-ID": "client-a"},
        )
        hidden_list = await self.client.get(
            "/api/v1/sessions",
            headers={"X-Client-ID": "client-b"},
        )
        concealed = await self.client.get(
            f"/api/v1/sessions/{session_id}",
            headers={"X-Client-ID": "client-b"},
        )
        invalid_agent = await self.client.post(
            "/api/v1/sessions",
            headers={"X-Client-ID": "client-b"},
            json=payload,
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(visible.json()["title"], "Project")
        self.assertEqual(len(visible_list.json()["sessions"]), 1)
        self.assertEqual(hidden_list.json(), {"sessions": []})
        self.assertEqual(concealed.status_code, 404)
        self.assertEqual(invalid_agent.status_code, 404)


if __name__ == "__main__":
    unittest.main()
