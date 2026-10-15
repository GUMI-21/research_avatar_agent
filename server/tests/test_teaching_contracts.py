"""First teaching batch: real course fixture and safe model-output contracts."""

import re
import unittest
from pathlib import Path

from pydantic import ValidationError

from app.schemas.avatar import AvatarControl
from app.schemas.chat import AvatarCommand, EmotionLabel
from app.schemas.teaching import CourseSelection, TeachingTurn
from app.services.skills import SkillCatalog


class TeachingContractsTest(unittest.TestCase):
    def test_defaults_select_english_led_hiragana_lesson(self) -> None:
        selection = CourseSelection()

        self.assertEqual(selection.course_id, "gojuon-en")
        self.assertEqual(selection.lesson_id, "hiragana-vowels")
        self.assertEqual(selection.instruction_language, "en")
        self.assertEqual(selection.target_language, "ja")
        self.assertEqual(CourseSelection(course_id=" gojuon-en ").course_id, "gojuon-en")

    def test_selection_rejects_paths_and_invalid_identifiers(self) -> None:
        for field in ("course_id", "lesson_id"):
            for value in ("", "  ", "../notes", "/tmp/lesson", "C:\\lesson", "course/file", "x" * 65):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    CourseSelection.model_validate({field: value})

    def test_selection_rejects_other_languages_and_arbitrary_paths(self) -> None:
        for payload in (
            {"instruction_language": "zh"},
            {"target_language": "en"},
            {"root_path": "/private"},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                CourseSelection.model_validate(payload)

    def test_reply_and_expression_survive_json_roundtrip(self) -> None:
        turn = TeachingTurn.model_validate({
            "schema_version": 1,
            "reply": "  That's right! い is i. Which character is u?  ",
            "avatar": {
                "expression": "happy", "action": "nod",
                "intensity": 0.35, "duration_ms": 800,
            },
        })

        self.assertEqual(turn.avatar.expression, EmotionLabel.HAPPY)
        self.assertEqual(turn.reply, "That's right! い is i. Which character is u?")
        self.assertEqual(TeachingTurn.model_validate_json(turn.model_dump_json()), turn)

    def test_missing_expression_defaults_are_neutral_and_independent(self) -> None:
        first = TeachingTurn(reply="Let's start with あ (a).")
        second = TeachingTurn(reply="Which character is i?")
        first.avatar.intensity = 0.5

        self.assertEqual(second.avatar, AvatarControl())
        self.assertEqual(second.avatar.expression, EmotionLabel.NEUTRAL)
        self.assertEqual(second.avatar.duration_ms, 0)

    def test_reply_is_required_nonblank_and_bounded(self) -> None:
        for payload in ({}, {"reply": " \n "}, {"reply": 12}, {"reply": "x" * 10_001}):
            with self.subTest(payload_type=list(payload)), self.assertRaises(ValidationError):
                TeachingTurn.model_validate(payload)

    def test_unknown_schema_fields_and_versions_are_rejected(self) -> None:
        for extra in ({"schema_version": 2}, {"thoughts": "private"}, {"tool": "shell"}):
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                TeachingTurn.model_validate({"reply": "Let's practice.", **extra})

    def test_intensity_requires_finite_bounded_numbers(self) -> None:
        for value in (float("nan"), float("inf"), -0.1, 1.1, True, "0.5", None):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                AvatarControl.model_validate({"intensity": value})
        for value in (0, 0.35, 1):
            with self.subTest(value=value):
                self.assertEqual(AvatarControl(intensity=value).intensity, value)

    def test_duration_requires_bounded_integer_milliseconds(self) -> None:
        for value in (-1, 60_001, True, 1.5, "800"):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                AvatarControl.model_validate({"duration_ms": value})
        self.assertEqual(AvatarControl(duration_ms=60_000).duration_ms, 60_000)

    def test_model_cannot_add_scripts_or_unknown_unity_controls(self) -> None:
        for avatar in (
            {"expression": "arbitrary_expression"},
            {"action": "execute_script"},
            {"script": "run()"},
            {"bone": "Head"},
            {"path": "/tmp/action"},
        ):
            with self.subTest(avatar=avatar), self.assertRaises(ValidationError):
                TeachingTurn.model_validate({"reply": "Try again.", "avatar": avatar})

    def test_legacy_avatar_contract_is_not_replaced(self) -> None:
        control = AvatarControl()
        legacy = AvatarCommand.model_validate(control.model_dump(mode="json"))

        self.assertEqual(legacy.expression, EmotionLabel.NEUTRAL)
        self.assertEqual(set(legacy.model_dump()), {"expression", "action", "intensity", "duration_ms"})

    def test_real_course_uses_existing_skill_parser_and_valid_output_example(self) -> None:
        courses = Path(__file__).resolve().parents[2] / "courses"
        selection = CourseSelection()
        course = SkillCatalog((courses,), 65_536).get(selection.course_id)

        self.assertIsNotNone(course)
        assert course is not None
        self.assertEqual(course.recommended_tools, ())
        self.assertEqual(len(course.version_hash), 64)
        self.assertIn(f"## {selection.lesson_id}\n", course.instructions)
        self.assertIn("Explain in English", course.instructions)
        self.assertIn("never claim to hear pronunciation", course.instructions)
        example = re.search(r"```json\n(.*?)\n```", course.instructions, re.DOTALL)
        self.assertIsNotNone(example)
        assert example is not None
        turn = TeachingTurn.model_validate_json(example.group(1))
        self.assertIn("い is i", turn.reply)


if __name__ == "__main__":
    unittest.main()
