"""Tests for client-scoped Agent HTTP routes."""

import unittest

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.database import Base, Database


class AgentRoutesTest(unittest.IsolatedAsyncioTestCase):
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

    async def test_create_and_list_agents_are_scoped_by_client(self) -> None:
        payload = {
            "name": "Personal",
            "system_prompt": "Help with my work.",
        }
        created = await self.client.post(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-a"},
            json=payload,
        )
        visible = await self.client.get(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-a"},
        )
        hidden = await self.client.get(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-b"},
        )
        agent_id = created.json()["id"]
        detail = await self.client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"X-Client-ID": "client-a"},
        )
        concealed = await self.client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"X-Client-ID": "client-b"},
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["client_id"], "client-a")
        self.assertEqual(len(visible.json()["agents"]), 1)
        self.assertEqual(hidden.json(), {"agents": []})
        self.assertEqual(detail.json()["id"], agent_id)
        self.assertEqual(concealed.status_code, 404)
        self.assertEqual(concealed.json(), {"detail": "Agent not found"})

    async def test_client_header_is_required(self) -> None:
        response = await self.client.get("/api/v1/agents")

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
