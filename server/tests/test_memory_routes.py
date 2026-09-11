"""Direct FastAPI contract tests for client-scoped Agent memories."""

import unittest

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.database import Base, Database


class MemoryRoutesTest(unittest.IsolatedAsyncioTestCase):
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

    async def test_memory_crud_is_client_scoped(self) -> None:
        headers = {"X-Client-ID": "client-a"}
        agent = await self.client.post("/api/v1/agents", headers=headers, json={
            "name": "Personal", "system_prompt": "Help me."
        })
        path = f"/api/v1/agents/{agent.json()['id']}/memories"

        created = await self.client.post(path, headers=headers, json={"content": "Prefer concise Chinese."})
        listed = await self.client.get(path, headers=headers)
        hidden = await self.client.get(path, headers={"X-Client-ID": "client-b"})
        memory_id = created.json()["id"]
        disabled = await self.client.patch(
            f"{path}/{memory_id}", headers=headers, json={"enabled": False}
        )
        deleted = await self.client.delete(f"{path}/{memory_id}", headers=headers)
        empty = await self.client.get(path, headers=headers)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(listed.json()["memories"][0]["content"], "Prefer concise Chinese.")
        self.assertEqual(hidden.json(), {"memories": []})
        self.assertFalse(disabled.json()["enabled"])
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(empty.json(), {"memories": []})


if __name__ == "__main__":
    unittest.main()
