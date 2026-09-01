"""Tests for client-scoped KnowledgeSource HTTP routes."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from app.api.router import api_router
from app.core.database import Base, Database


class KnowledgeRoutesTest(unittest.IsolatedAsyncioTestCase):
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

    async def test_create_list_and_detail_are_client_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            headers = {"X-Client-ID": "client-a"}
            with patch("app.services.knowledge.log"):
                created = await self.client.post(
                    "/api/v1/knowledge/sources",
                    headers=headers,
                    json={"name": "Notes", "root_path": temp_dir},
                )
            source_id = created.json()["id"]
            visible = await self.client.get(
                "/api/v1/knowledge/sources",
                headers=headers,
            )
            hidden = await self.client.get(
                "/api/v1/knowledge/sources",
                headers={"X-Client-ID": "client-b"},
            )
            concealed = await self.client.get(
                f"/api/v1/knowledge/sources/{source_id}",
                headers={"X-Client-ID": "client-b"},
            )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["root_path"], str(Path(temp_dir).resolve()))
        self.assertEqual(len(visible.json()["sources"]), 1)
        self.assertEqual(hidden.json(), {"sources": []})
        self.assertEqual(concealed.status_code, 404)

    async def test_invalid_and_duplicate_directories_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            headers = {"X-Client-ID": "client-a"}
            with patch("app.services.knowledge.log"):
                first = await self.client.post(
                    "/api/v1/knowledge/sources",
                    headers=headers,
                    json={"name": "Notes", "root_path": temp_dir},
                )
            duplicate = await self.client.post(
                "/api/v1/knowledge/sources",
                headers=headers,
                json={"name": "Other", "root_path": temp_dir},
            )
            missing = await self.client.post(
                "/api/v1/knowledge/sources",
                headers=headers,
                json={"name": "Missing", "root_path": f"{temp_dir}/missing"},
            )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(missing.status_code, 400)


if __name__ == "__main__":
    unittest.main()
