"""Course discovery validates real files while retaining atomic snapshots."""

import hashlib
import asyncio
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.core.settings import CourseSettings, SERVER_ROOT, Settings
from app.schemas.teaching import CourseSelection
from app.services.courses import (
    CourseCatalog, CourseCatalogError, CourseSelectionNotFoundError,
)
from app.services.skills import SkillCatalog


def write_course(root: Path, course_id="gojuon-en", *, metadata=None, body=None) -> Path:
    details = {
        "display_name": "Kana in English",
        "instruction_language": "en", "target_language": "ja",
        "lesson_ids": ["hiragana-vowels"], "recommended_tools": [],
    }
    if metadata is not None:
        details.update(metadata)
    header = {"name": course_id, "description": "Learn kana.", "metadata": details}
    path = root / course_id / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n" + yaml.safe_dump(header) + "---\n"
        + (body if body is not None else "## hiragana-vowels\nLearn あ (a).\n"),
        encoding="utf-8",
    )
    return path


class CourseCatalogTest(unittest.TestCase):
    def test_real_course_loads_all_declared_lessons_with_byte_hash(self) -> None:
        root = SERVER_ROOT.parent / "courses"
        course = CourseCatalog((root,)).resolve(CourseSelection())

        self.assertEqual(course.id, "gojuon-en")
        self.assertEqual(course.instruction_language, "en")
        self.assertEqual(course.target_language, "ja")
        self.assertEqual(course.lesson_ids, ("hiragana-vowels", "hiragana-rows", "katakana-review"))
        self.assertIn("## Teaching behavior", course.instructions)
        self.assertEqual(course.version_hash, hashlib.sha256((root / course.id / "SKILL.md").read_bytes()).hexdigest())
        with self.assertRaises(FrozenInstanceError):
            course.name = "Changed"

    def test_only_allowed_directories_are_discovered_and_order_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as allowed, tempfile.TemporaryDirectory() as outside:
            root = Path(allowed)
            write_course(root, "z-course")
            write_course(root, "a-course")
            write_course(Path(outside), "private-course")
            catalog = CourseCatalog((root,))

            self.assertEqual(tuple(course.id for course in catalog.list()), ("a-course", "z-course"))
            self.assertIsNone(catalog.get("private-course"))
            self.assertIsNone(catalog.get("../private-course"))

    def test_unknown_course_or_undeclared_heading_cannot_be_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_course(root, body="## hiragana-vowels\nあ\n## supporting-notes\nNotes.")
            catalog = CourseCatalog((root,))
            for selection in (
                CourseSelection(course_id="missing"),
                CourseSelection(lesson_id="supporting-notes"),
            ):
                with self.subTest(selection=selection), self.assertRaises(CourseSelectionNotFoundError):
                    catalog.resolve(selection)

    def test_refresh_versions_content_without_mutating_previous_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_course(root)
            catalog = CourseCatalog((root,))
            first = catalog.resolve(CourseSelection())
            write_course(root, body="## hiragana-vowels\nRevised practice: い (i).")

            # Existing turns keep the first immutable snapshot until explicit refresh.
            self.assertIs(catalog.resolve(CourseSelection()), first)
            second = catalog.refresh()[0]
            self.assertNotEqual(first.version_hash, second.version_hash)
            self.assertIn("Learn あ", first.instructions)
            self.assertIn("Revised practice", second.instructions)

    def test_failed_refresh_preserves_entire_previous_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_course(root)
            catalog = CourseCatalog((root,))
            first = catalog.list()
            write_course(root, "bad-course", metadata={"instruction_language": "zh"})

            with self.assertRaises(CourseCatalogError):
                catalog.refresh()
            self.assertEqual(catalog.list(), first)
            self.assertIsNone(catalog.get("bad-course"))

    def test_rejects_invalid_languages_lesson_lists_and_ids(self) -> None:
        for metadata in (
            {"instruction_language": "zh"}, {"target_language": "en"},
            {"instruction_language": None}, {"target_language": None},
            {"lesson_ids": []}, {"lesson_ids": "hiragana-vowels"},
            {"lesson_ids": None}, {"lesson_ids": [None]},
            {"lesson_ids": ["../file"]}, {"lesson_ids": ["missing-heading"]},
            {"lesson_ids": ["hiragana-vowels", "hiragana-vowels"]},
            {"lesson_ids": ["hiragana-vowels", " hiragana-vowels "]},
            {"lesson_ids": ["hiragana-vowels"] * 51},
        ):
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as directory:
                write_course(Path(directory), metadata=metadata)
                with self.assertRaises(CourseCatalogError):
                    CourseCatalog((Path(directory),))

    def test_rejects_duplicate_course_ids_across_roots(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            write_course(Path(first))
            write_course(Path(second))
            with self.assertRaises(CourseCatalogError):
                CourseCatalog((Path(first), Path(second)))

    def test_rejects_duplicate_lesson_headings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            write_course(Path(directory), body="## hiragana-vowels\nあ\n## hiragana-vowels\nい")
            with self.assertRaises(CourseCatalogError):
                CourseCatalog((Path(directory),))

    def test_code_fences_cannot_supply_fake_lesson_headings(self) -> None:
        for fence in ("```", "~~~", "````"):
            with self.subTest(fence=fence), tempfile.TemporaryDirectory() as directory:
                body = fence + "markdown\n## hiragana-vowels\nあ\n" + fence
                write_course(Path(directory), body=body)
                with self.assertRaises(CourseCatalogError):
                    CourseCatalog((Path(directory),))

    def test_nested_short_fences_do_not_end_a_longer_example(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_course(root, body="````markdown\n```\n## fake\n```\n````\n## hiragana-vowels\nあ")
            self.assertEqual(CourseCatalog((root,)).resolve(CourseSelection()).lesson_ids, ("hiragana-vowels",))

    def test_rejects_oversized_non_utf8_and_malformed_yaml_files(self) -> None:
        for raw, limit in (
            (b"x" * 200, 100),
            (b"\xff\xfe", 100),
            (b"---\nname: [private-invalid-marker\n---\nbody", 100),
        ):
            with self.subTest(raw_prefix=raw[:4]), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "SKILL.md").write_bytes(raw)
                with self.assertRaises(CourseCatalogError) as raised:
                    CourseCatalog((root,), limit)
                self.assertNotIn("private-invalid-marker", str(raised.exception))

    def test_symlink_file_cannot_escape_allowed_root(self) -> None:
        with tempfile.TemporaryDirectory() as allowed, tempfile.TemporaryDirectory() as outside:
            target = write_course(Path(outside))
            link = Path(allowed) / "SKILL.md"
            try:
                link.symlink_to(target)
            except OSError as error:
                if getattr(error, "winerror", None) == 1314:
                    self.skipTest("Windows symlink privileges are unavailable")
                raise
            with self.assertRaises(CourseCatalogError):
                CourseCatalog((Path(allowed),))

    def test_disabled_or_missing_course_directories_are_empty(self) -> None:
        self.assertEqual(CourseCatalog(()).list(), ())
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(CourseCatalog((Path(directory) / "missing",)).list(), ())

    def test_shared_skill_metadata_is_retained_without_changing_tool_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_course(root)
            skill = SkillCatalog((root,), 65_536).get("gojuon-en")
            assert skill is not None
            self.assertEqual(skill.metadata["instruction_language"], "en")
            self.assertEqual(skill.recommended_tools, ())

    def test_course_settings_have_independent_root_and_bounded_size(self) -> None:
        settings = CourseSettings()
        self.assertEqual(settings.directories, (SERVER_ROOT.parent / "courses",))
        self.assertEqual(CourseSettings(directories=()).directories, ())
        for value in (0, 1_048_577):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                CourseSettings(max_file_bytes=value)

    def test_app_loads_courses_separately_from_general_agent_skills(self) -> None:
        from app.main import create_app

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_course(root)
            config = yaml.safe_load((SERVER_ROOT / "config" / "config_example.yaml").read_text(encoding="utf-8"))
            config.update(environment="debug", courses={"directories": [str(root)]})
            app = create_app(Settings.model_validate(config))
            try:
                self.assertEqual(app.state.course_catalog.resolve(CourseSelection()).id, "gojuon-en")
                self.assertIsNone(app.state.skill_catalog.get("gojuon-en"))
            finally:
                asyncio.run(app.state.database.dispose())


if __name__ == "__main__":
    unittest.main()
