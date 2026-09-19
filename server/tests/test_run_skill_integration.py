"""Integration coverage for project Skill injection and Run auditing."""

import unittest
from collections.abc import AsyncIterator
from pathlib import Path

from app.adapters.agent import RuntimeEvent, RuntimeEventType, RuntimeRequest
from app.core.database import Base, Database
from app.repositories import AgentRepository, RunRepository, SessionRepository
from app.services import RunExecutionService
from app.services.runtime_registry import RuntimeRegistry
from app.services.skills import SkillCatalog


class CapturingRuntime:
    request: RuntimeRequest | None = None

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        type(self).request = request
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        yield RuntimeEvent(
            type=RuntimeEventType.ASSISTANT_DELTA, payload={"text": "已规划"}
        )
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)


class RunSkillIntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_real_daily_planning_skill_is_injected_and_audited(self) -> None:
        database = Database("sqlite+aiosqlite:///:memory:")
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            async with database.session() as session:
                agents = AgentRepository(session)
                agent = await agents.create(
                    "client-a",
                    name="Planner",
                    system_prompt="Help plan the user''s day.",
                    runtime="native",
                )
                await agents.replace_skills(
                    "client-a", agent.id, ["daily-planning"]
                )
                conversation = await SessionRepository(session).create(
                    "client-a", agent.id
                )
                await session.commit()

                registry = RuntimeRegistry()
                registry.register("native", CapturingRuntime)
                skill_root = Path(__file__).parents[1] / "skills"
                catalog = SkillCatalog((skill_root,), 65_536)
                streamed = [
                    item
                    async for item in RunExecutionService(
                        session, registry, skill_catalog=catalog
                    ).stream("client-a", conversation.id, "帮我规划今天")
                ]

                request = CapturingRuntime.request
                self.assertIsNotNone(request)
                assert request is not None
                self.assertIn("每日工作规划", request.system_prompt)
                self.assertIn("calendar_list_events", request.system_prompt)
                self.assertIn("preserve every permission", request.system_prompt)
                run = await RunRepository(session).get(
                    "client-a", streamed[0].run_id
                )
                self.assertIsNotNone(run)
                assert run is not None
                self.assertEqual(run.skill_versions[0]["id"], "daily-planning")
                self.assertEqual(
                    len(run.skill_versions[0]["version_hash"]), 64
                )
        finally:
            await database.dispose()


if __name__ == "__main__":
    unittest.main()
