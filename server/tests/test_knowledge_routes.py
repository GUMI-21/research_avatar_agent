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

    async def test_sync_returns_incremental_counts_and_is_client_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "first.md").write_text("# 第一篇", encoding="utf-8")
            Path(temp_dir, "second.md").write_text("# 第二篇", encoding="utf-8")
            headers = {"X-Client-ID": "client-a"}
            with patch("app.services.knowledge.log"):
                created = await self.client.post(
                    "/api/v1/knowledge/sources",
                    headers=headers,
                    json={"name": "Notes", "root_path": temp_dir},
                )
                source_id = created.json()["id"]
                first = await self.client.post(
                    f"/api/v1/knowledge/sources/{source_id}/sync",
                    headers=headers,
                )
                second = await self.client.post(
                    f"/api/v1/knowledge/sources/{source_id}/sync",
                    headers=headers,
                )
                concealed = await self.client.post(
                    f"/api/v1/knowledge/sources/{source_id}/sync",
                    headers={"X-Client-ID": "client-b"},
                )
                first_page = await self.client.get(
                    f"/api/v1/knowledge/sources/{source_id}/documents",
                    headers=headers,
                    params={"limit": 1},
                )
                first_document = first_page.json()["documents"][0]
                second_page = await self.client.get(
                    f"/api/v1/knowledge/sources/{source_id}/documents",
                    headers=headers,
                    params={
                        "limit": 1,
                        "after_path": first_page.json()["next_cursor"],
                    },
                )
                detail = await self.client.get(
                    f"/api/v1/knowledge/sources/{source_id}/documents/"
                    f"{first_document['id']}",
                    headers=headers,
                )
                hidden_documents = await self.client.get(
                    f"/api/v1/knowledge/sources/{source_id}/documents",
                    headers={"X-Client-ID": "client-b"},
                )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()["created"], 2)
        self.assertEqual(first.json()["chunks"], 0)
        self.assertEqual(first.json()["status"], "ready")
        self.assertEqual(second.json()["unchanged"], 2)
        self.assertEqual(concealed.status_code, 404)
        self.assertTrue(first_page.json()["has_more"])
        self.assertEqual(first_page.json()["next_cursor"], "first.md")
        self.assertEqual(second_page.json()["documents"][0]["relative_path"], "second.md")
        self.assertFalse(second_page.json()["has_more"])
        self.assertEqual(detail.json()["title"], "第一篇")
        self.assertEqual(hidden_documents.status_code, 404)

    async def test_sync_failure_returns_stable_error_and_updates_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "invalid.md").write_text(
                "---\ntags: [broken\n---\nbody", encoding="utf-8"
            )
            headers = {"X-Client-ID": "client-a"}
            with patch("app.services.knowledge.log"):
                created = await self.client.post(
                    "/api/v1/knowledge/sources",
                    headers=headers,
                    json={"name": "Invalid", "root_path": temp_dir},
                )
                source_id = created.json()["id"]
                response = await self.client.post(
                    f"/api/v1/knowledge/sources/{source_id}/sync",
                    headers=headers,
                )
            source = await self.client.get(
                f"/api/v1/knowledge/sources/{source_id}",
                headers=headers,
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"], "Knowledge source sync failed")
        self.assertEqual(source.json()["sync_status"], "failed")


if __name__ == "__main__":
    unittest.main()
