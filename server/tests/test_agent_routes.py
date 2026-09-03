"""Tests for client-scoped Agent HTTP routes."""

import unittest

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.database import Base, Database
from app.models import KnowledgeSourceRecord


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

    async def test_duplicate_name_conflicts_only_within_client(self) -> None:
        payload = {
            "name": "Personal",
            "system_prompt": "Help with my work.",
        }
        first = await self.client.post(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-a"},
            json=payload,
        )
        duplicate = await self.client.post(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-a"},
            json=payload,
        )
        other_client = await self.client.post(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-b"},
            json=payload,
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(
            duplicate.json(),
            {"detail": "Agent name already exists"},
        )
        self.assertEqual(other_client.status_code, 201)

    async def test_agent_knowledge_sources_are_client_scoped(self) -> None:
        async with self.database.session() as session:
            own_source = KnowledgeSourceRecord(
                client_id="client-a", name="Own Notes", root_path="/notes/a"
            )
            foreign_source = KnowledgeSourceRecord(
                client_id="client-b", name="Other Notes", root_path="/notes/b"
            )
            session.add_all([own_source, foreign_source])
            await session.commit()

        created = await self.client.post(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-a"},
            json={
                "name": "Researcher",
                "system_prompt": "Use my notes.",
                "knowledge_source_ids": [own_source.id],
            },
        )
        concealed = await self.client.post(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-a"},
            json={
                "name": "Invalid",
                "system_prompt": "Do not cross client boundaries.",
                "knowledge_source_ids": [foreign_source.id],
            },
        )
        detail = await self.client.get(
            f"/api/v1/agents/{created.json()['id']}",
            headers={"X-Client-ID": "client-a"},
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["knowledge_source_ids"], [own_source.id])
        self.assertEqual(detail.json()["knowledge_source_ids"], [own_source.id])
        self.assertEqual(concealed.status_code, 404)
        self.assertEqual(concealed.json()["detail"], "Knowledge source not found")


if __name__ == "__main__":
    unittest.main()
