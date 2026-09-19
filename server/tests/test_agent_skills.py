"""Tests for client-scoped Agent Skill bindings."""

import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi import FastAPI
from sqlalchemy import select

from app.api.router import api_router
from app.core.database import Base, Database
from app.models import AgentSkillRecord
from app.services.skills import SkillCatalog


class AgentSkillsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        skill = root / "daily_planning" / "SKILL.md"
        skill.parent.mkdir()
        skill.write_text(
            """---
id: daily_planning
name: Daily planning
description: Plan the day.
applicable_scenarios: [planning]
recommended_tools: [calendar_list_events]
---
Use the calendar tools through the normal approval flow.
""",
            encoding="utf-8",
        )
        app = FastAPI()
        app.state.database = self.database
        app.state.skill_catalog = SkillCatalog((root,), 10_000)
        app.include_router(api_router)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        await self.database.dispose()
        self.directory.cleanup()

    async def test_replaces_bindings_and_rejects_cross_client_access(self) -> None:
        agent = await self.client.post(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-a"},
            json={"name": "Personal", "system_prompt": "Help me."},
        )
        agent_id = agent.json()["id"]

        updated = await self.client.put(
            f"/api/v1/agents/{agent_id}/skills",
            headers={"X-Client-ID": "client-a"},
            json={"skill_ids": ["daily_planning"]},
        )
        visible = await self.client.get(
            f"/api/v1/agents/{agent_id}",
            headers={"X-Client-ID": "client-a"},
        )
        hidden = await self.client.put(
            f"/api/v1/agents/{agent_id}/skills",
            headers={"X-Client-ID": "client-b"},
            json={"skill_ids": []},
        )

        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["skill_ids"], ["daily_planning"])
        self.assertEqual(visible.json()["skill_ids"], ["daily_planning"])
        self.assertEqual(hidden.status_code, 404)
        async with self.database.session() as session:
            records = (await session.execute(select(AgentSkillRecord))).scalars().all()
        self.assertEqual(
            [(record.client_id, record.agent_id, record.skill_id) for record in records],
            [("client-a", agent_id, "daily_planning")],
        )

    async def test_rejects_unknown_skill_and_can_clear_bindings(self) -> None:
        agent = await self.client.post(
            "/api/v1/agents",
            headers={"X-Client-ID": "client-a"},
            json={"name": "Personal", "system_prompt": "Help me."},
        )
        agent_id = agent.json()["id"]
        unknown = await self.client.put(
            f"/api/v1/agents/{agent_id}/skills",
            headers={"X-Client-ID": "client-a"},
            json={"skill_ids": ["missing_skill"]},
        )
        cleared = await self.client.put(
            f"/api/v1/agents/{agent_id}/skills",
            headers={"X-Client-ID": "client-a"},
            json={"skill_ids": []},
        )

        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json()["skill_ids"], [])


if __name__ == "__main__":
    unittest.main()
