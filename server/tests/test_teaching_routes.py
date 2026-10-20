"""Public teaching bindings validate catalog, Native runtime and client boundaries."""

import unittest
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.router import api_router
from app.core.database import Base, Database
from app.models import MessageRecord, RunRecord
from app.repositories import AgentRepository, SessionRepository, TeachingRepository
from app.schemas.teaching import CourseSelection
from app.services.courses import CourseCatalog
from app.services.teaching import TeachingBindingConflictError, TeachingService


class TeachingRoutesTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = Database("sqlite+aiosqlite:///:memory:")
        async with self.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.course_root = Path(__file__).resolve().parents[2] / "courses"
        self.catalog = CourseCatalog((self.course_root,))
        self.app = FastAPI()
        self.app.state.database = self.database
        self.app.state.course_catalog = self.catalog
        self.app.include_router(api_router)
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://testserver",
            headers={"X-Client-ID": "client-a"},
        )
        self.session_id = await self._conversation("native")
        self.path = f"/api/v1/avatar/sessions/{self.session_id}/teaching"

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        await self.database.dispose()

    async def _conversation(self, runtime: str) -> str:
        async with self.database.session() as session:
            agent = await AgentRepository(session).create(
                "client-a", name=runtime, system_prompt="Teach kana.", runtime=runtime,
            )
            conversation = await SessionRepository(session).create("client-a", agent.id)
            await session.commit()
            return conversation.id

    async def test_course_list_exposes_only_public_metadata(self) -> None:
        response = await self.client.get("/api/v1/avatar/courses")
        self.assertEqual(response.status_code, 200)
        course = response.json()["courses"][0]
        self.assertEqual(set(course), {
            "id", "name", "description", "lesson_ids", "version_hash",
            "instruction_language", "target_language",
        })
        self.assertEqual(course["id"], "gojuon-en")
        self.assertIn("hiragana-vowels", course["lesson_ids"])
        self.assertEqual((course["instruction_language"], course["target_language"]), ("en", "ja"))
        self.assertEqual(course["version_hash"], sha256(
            (self.course_root / "gojuon-en" / "SKILL.md").read_bytes()
        ).hexdigest())
        self.assertNotIn(str(self.course_root), response.text)
        self.app.state.course_catalog = CourseCatalog(())
        self.assertEqual((await self.client.get("/api/v1/avatar/courses")).json(), {"courses": []})

    async def test_all_routes_require_nonblank_client_header(self) -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://testserver",
        ) as anonymous:
            for headers in ({}, {"X-Client-ID": " "}):
                for method, path, kwargs in (
                    ("GET", "/api/v1/avatar/courses", {}),
                    ("GET", self.path, {}), ("PUT", self.path, {"json": {}}),
                ):
                    with self.subTest(headers=headers, method=method, path=path):
                        response = await anonymous.request(method, path, headers=headers, **kwargs)
                        self.assertEqual(response.status_code, 422)

    async def test_binding_is_durable_idempotent_and_does_not_execute_model(self) -> None:
        self.assertEqual((await self.client.get(self.path)).status_code, 404)
        created = await self.client.put(self.path, json={})
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["session_id"], self.session_id)
        self.assertEqual(created.json()["completed_turns"], 0)
        self.assertEqual(created.json()["state_version"], 1)
        self.assertTrue(created.json()["created_at"].endswith("Z"))
        self.assertEqual((await self.client.get(self.path)).json(), created.json())
        self.assertEqual(created.json()["course_version"], self.catalog.get("gojuon-en").version_hash)
        self.assertNotIn("client_id", created.json())
        async with self.database.session() as session:
            record = await TeachingRepository(session).get("client-a", self.session_id)
            record.completed_turns = 2
            record.state_version = 3
            await session.commit()
        before = (await self.client.get(self.path)).json()
        repeated = await self.client.put(self.path, json={})
        self.assertEqual(repeated.json(), before)
        async with self.database.session() as session:
            for model in (RunRecord, MessageRecord):
                self.assertEqual(await session.scalar(select(func.count()).select_from(model)), 0)

    async def test_missing_and_cross_client_sessions_are_not_visible(self) -> None:
        self.assertEqual((await self.client.put(self.path, json={})).status_code, 200)
        for method in ("GET", "PUT"):
            for path, headers in (
                (self.path, {"X-Client-ID": "client-b"}),
                ("/api/v1/avatar/sessions/missing/teaching", {"X-Client-ID": "client-a"}),
            ):
                with self.subTest(method=method, path=path, headers=headers):
                    kwargs = {"json": {}} if method == "PUT" else {}
                    response = await self.client.request(method, path, headers=headers, **kwargs)
                    self.assertEqual(response.status_code, 404)
        self.assertEqual((await self.client.get(self.path)).status_code, 200)

    async def test_non_native_sessions_cannot_bind(self) -> None:
        codex_session = await self._conversation("codex")
        path = f"/api/v1/avatar/sessions/{codex_session}/teaching"
        response = await self.client.put(path, json={})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"], "Teaching requires a Native Agent")
        self.assertEqual((await self.client.get(path)).status_code, 404)

    async def test_agent_reference_must_also_belong_to_client(self) -> None:
        async with self.database.session() as session:
            foreign_agent = await AgentRepository(session).create(
                "client-b", name="Other teacher", system_prompt="Teach.",
            )
            conversation = await SessionRepository(session).get("client-a", self.session_id)
            conversation.agent_id = foreign_agent.id
            await session.commit()
        self.assertEqual((await self.client.put(self.path, json={})).status_code, 404)
        self.assertEqual((await self.client.get(self.path)).status_code, 404)

    async def test_unknown_courses_lessons_and_invalid_inputs_do_not_bind(self) -> None:
        for payload, status in (
            ({"course_id": "missing"}, 404), ({"lesson_id": "missing"}, 404),
            ({"course_id": "../../private"}, 422), ({"instruction_language": "zh"}, 422),
            ({"client_id": "client-b"}, 422), ({"course_version": "forged"}, 422),
            ({"completed_turns": 99}, 422), ({"state_version": 99}, 422),
        ):
            with self.subTest(payload=payload):
                response = await self.client.put(self.path, json=payload)
                self.assertEqual(response.status_code, status)
                self.assertEqual((await self.client.get(self.path)).status_code, 404)

    async def test_rebinding_and_script_changes_preserve_existing_state(self) -> None:
        original = await self.client.put(self.path, json={})
        course = self.catalog.get("gojuon-en")
        different = await self.client.put(self.path, json={"lesson_id": course.lesson_ids[1]})
        self.assertEqual(different.status_code, 409)
        changed_catalog = Mock(spec=CourseCatalog)
        changed_catalog.resolve.return_value = replace(course, version_hash="b" * 64)
        self.app.state.course_catalog = changed_catalog
        self.assertEqual((await self.client.put(self.path, json={})).status_code, 409)
        self.assertEqual((await self.client.get(self.path)).json(), original.json())
        self.app.state.course_catalog = CourseCatalog(())
        self.assertEqual((await self.client.put(self.path, json={})).status_code, 404)
        self.assertEqual((await self.client.get(self.path)).json(), original.json())

    async def test_service_rolls_back_commit_failure(self) -> None:
        async with self.database.session() as session:
            with patch.object(session, "commit", AsyncMock(side_effect=RuntimeError("commit failed"))):
                with self.assertRaisesRegex(RuntimeError, "commit failed"):
                    await TeachingService(session, self.catalog).bind("client-a", self.session_id, CourseSelection())
            self.assertIsNone(await TeachingRepository(session).get("client-a", self.session_id))

    async def test_integrity_conflict_has_safe_error_and_rollback(self) -> None:
        error = IntegrityError("private statement", {}, Exception("private details"))
        async with self.database.session() as session:
            with patch.object(TeachingRepository, "create", AsyncMock(side_effect=error)):
                with self.assertRaisesRegex(TeachingBindingConflictError, "retry the request") as caught:
                    await TeachingService(session, self.catalog).bind("client-a", self.session_id, CourseSelection())
            self.assertNotIn("private", str(caught.exception))
            self.assertIsNone(await TeachingRepository(session).get("client-a", self.session_id))
