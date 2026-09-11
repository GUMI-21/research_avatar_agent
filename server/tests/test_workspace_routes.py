"""Direct API tests for unique local workspace identities."""

import unittest

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.database import Base, Database


class WorkspaceRoutesTest(unittest.IsolatedAsyncioTestCase):
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

    async def test_username_is_normalized_unique_and_queryable(self) -> None:
        created = await self.client.post(
            "/api/v1/workspaces", json={"username": " Alice "}
        )
        duplicate = await self.client.post(
            "/api/v1/workspaces", json={"username": "ALICE"}
        )
        loaded = await self.client.get("/api/v1/workspaces/Alice")
        missing = await self.client.get("/api/v1/workspaces/missing")
        invalid = await self.client.post(
            "/api/v1/workspaces", json={"username": "bad user"}
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["username"], "alice")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(loaded.json()["username"], "alice")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(invalid.status_code, 422)

    async def test_registered_usernames_remain_data_scopes(self) -> None:
        for username in ("alice", "bob"):
            await self.client.post(
                "/api/v1/workspaces", json={"username": username}
            )
            await self.client.post(
                "/api/v1/agents",
                headers={"X-Client-ID": username},
                json={"name": "Personal", "system_prompt": f"Help {username}."},
            )

        alice = await self.client.get(
            "/api/v1/agents", headers={"X-Client-ID": "alice"}
        )
        bob = await self.client.get(
            "/api/v1/agents", headers={"X-Client-ID": "bob"}
        )

        self.assertEqual(alice.json()["agents"][0]["system_prompt"], "Help alice.")
        self.assertEqual(bob.json()["agents"][0]["system_prompt"], "Help bob.")


if __name__ == "__main__":
    unittest.main()
