"""Tests for safe Skill discovery and public catalog metadata."""

import tempfile
import unittest
from pathlib import Path

import httpx
from fastapi import FastAPI

from app.api.routes import skills
from app.services.skills import SkillCatalog, SkillCatalogError


def write_skill(
    root: Path,
    skill_id: str = "daily_planning",
    *,
    tools: str = "  - calendar_list_events",
    instructions: str = "Plan the day without bypassing tool approval.",
) -> Path:
    path = root / skill_id / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "\n".join((
            "---",
            f"id: {skill_id}",
            "name: Daily planning",
            "description: Plan work from the user's calendar.",
            "applicable_scenarios:",
            "  - daily planning",
            "recommended_tools:",
            tools,
            "---",
            instructions,
        )),
        encoding="utf-8",
    )
    return path


class SkillCatalogTest(unittest.IsolatedAsyncioTestCase):
    async def test_discovers_versions_and_exposes_only_public_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = write_skill(root)
            catalog = SkillCatalog((root,), 10_000)
            first = catalog.list()[0]
            self.assertEqual(first.id, "daily_planning")
            self.assertEqual(first.recommended_tools, ("calendar_list_events",))
            self.assertIn("without bypassing", first.instructions)

            app = FastAPI()
            app.state.skill_catalog = catalog
            app.include_router(skills.router, prefix="/api/v1")
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://testserver",
            ) as client:
                response = await client.get(
                    "/api/v1/skills", headers={"X-Client-ID": "client-a"}
                )
            self.assertEqual(response.status_code, 200)
            public = response.json()["skills"][0]
            self.assertEqual(public["id"], "daily_planning")
            self.assertNotIn("instructions", public)
            self.assertNotIn("path", public)

            path.write_text(path.read_text(encoding="utf-8") + "\nNew rule.", encoding="utf-8")
            catalog.refresh()
            self.assertNotEqual(catalog.list()[0].version_hash, first.version_hash)

    async def test_rejects_invalid_duplicate_and_oversized_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root, tools="  - Invalid Tool")
            with self.assertRaisesRegex(SkillCatalogError, "tool name"):
                SkillCatalog((root,), 10_000)

        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first_root, second_root = Path(first_dir), Path(second_dir)
            write_skill(first_root, "duplicate")
            write_skill(second_root, "duplicate")
            with self.assertRaisesRegex(SkillCatalogError, "Duplicate"):
                SkillCatalog((first_root, second_root), 10_000)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_skill(root)
            with self.assertRaisesRegex(SkillCatalogError, "too large"):
                SkillCatalog((root,), 10)


if __name__ == "__main__":
    unittest.main()
