"""Tests for client-scoped usage summary and recent Run APIs."""

import unittest
from decimal import Decimal

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.database import Base, Database
from app.repositories import AgentRepository, RunRepository, SessionRepository


class UsageRoutesTest(unittest.IsolatedAsyncioTestCase):
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

    async def _add_run(self, client_id: str, *, failed: bool) -> str:
        async with self.database.session() as session:
            agent = await AgentRepository(session).create(
                client_id,
                name="Personal-failed" if failed else "Personal-completed",
                system_prompt="Help me.",
            )
            conversation = await SessionRepository(session).create(
                client_id,
                agent.id,
            )
            runs = RunRepository(session)
            run = await runs.create(
                client_id,
                conversation.id,
                agent.id,
                runtime="native",
            )
            await runs.set_usage(
                client_id,
                run.id,
                provider="openai",
                model="gpt-5.6-luna",
                input_tokens=100,
                output_tokens=20,
                cache_read_tokens=10,
                cache_write_tokens=0,
                cost_usd=Decimal("0.001000"),
                cost_status="estimated",
            )
            await runs.set_status(
                client_id,
                run.id,
                "failed" if failed else "completed",
                duration_ms=200,
                time_to_first_token_ms=None if failed else 50,
            )
            await session.commit()
            return run.id

    async def test_summary_and_recent_runs_are_client_scoped(self) -> None:
        first_id = await self._add_run("client-a", failed=False)
        second_id = await self._add_run("client-a", failed=True)
        await self._add_run("client-b", failed=False)
        headers = {"X-Client-ID": "client-a"}

        summary = await self.client.get("/api/v1/usage/summary", headers=headers)
        recent = await self.client.get(
            "/api/v1/usage/runs?limit=10",
            headers=headers,
        )

        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["run_count"], 2)
        self.assertEqual(summary.json()["failed_count"], 1)
        self.assertEqual(summary.json()["unavailable_cost_count"], 0)
        self.assertEqual(summary.json()["input_tokens"], 200)
        self.assertEqual(summary.json()["cost_usd"], "0.002000")
        self.assertEqual(summary.json()["average_duration_ms"], 200)
        self.assertEqual(
            {run["id"] for run in recent.json()["runs"]},
            {first_id, second_id},
        )

        empty = await self.client.get(
            "/api/v1/usage/summary",
            headers={"X-Client-ID": "client-c"},
        )
        self.assertEqual(empty.json()["run_count"], 0)
        self.assertEqual(empty.json()["cost_usd"], "0.000000")
        self.assertIsNone(empty.json()["average_duration_ms"])


if __name__ == "__main__":
    unittest.main()
