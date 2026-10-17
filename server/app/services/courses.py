"""Discover versioned teaching scripts through the shared Skill parser."""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.schemas.teaching import CourseSelection
from app.services.skills import SkillCatalog, SkillCatalogError, SkillDefinition
from logs import log


class CourseCatalogError(ValueError):
    pass


class CourseSelectionNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class CourseDefinition:
    id: str
    name: str
    description: str
    lesson_ids: tuple[str, ...]
    instructions: str
    version_hash: str
    instruction_language: str = "en"
    target_language: str = "ja"


def _lesson_headings(instructions: str) -> list[str]:
    headings: list[str] = []
    fence = ""
    for line in instructions.splitlines():
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if marker:
            token, suffix = marker.groups()
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence) and not suffix.strip():
                fence = ""
        elif not fence and (heading := re.fullmatch(r"##[ \t]+([a-z][a-z0-9_-]{0,63})[ \t]*", line)):
            headings.append(heading[1])
    return headings


class CourseCatalog:
    def __init__(self, directories: tuple[Path, ...], max_file_bytes: int = 65_536) -> None:
        self._directories = directories
        self._max_file_bytes = max_file_bytes
        self._courses: dict[str, CourseDefinition] = {}
        _ = self.refresh()

    def refresh(self) -> tuple[CourseDefinition, ...]:
        # Build separately: a failed refresh must preserve the previous snapshot.
        try:
            skills = SkillCatalog(self._directories, self._max_file_bytes).list()
            discovered = {skill.id: self._parse(skill) for skill in skills}
        except (CourseCatalogError, SkillCatalogError, ValidationError, yaml.YAMLError, OSError) as error:
            log.warning("course_catalog_refresh_failed business=avatar_teaching error_type={}", type(error).__name__)
            raise CourseCatalogError("Course discovery or validation failed") from error
        self._courses = discovered
        log.info("course_catalog_refreshed business=avatar_teaching courses={} lessons={}",
                 len(discovered), sum(len(course.lesson_ids) for course in discovered.values()))
        return self.list()

    @staticmethod
    def _parse(skill: SkillDefinition) -> CourseDefinition:
        lessons = skill.metadata.get("lesson_ids")
        if not isinstance(lessons, list) or not 1 <= len(lessons) <= 50:
            raise CourseCatalogError("Course must declare between 1 and 50 lesson IDs")
        selections = [CourseSelection.model_validate({
            "course_id": skill.id, "lesson_id": lesson,
            "instruction_language": skill.metadata.get("instruction_language"),
            "target_language": skill.metadata.get("target_language"),
        }) for lesson in lessons]
        lesson_ids = tuple(selection.lesson_id for selection in selections)
        headings = _lesson_headings(skill.instructions)
        if len(set(lesson_ids)) != len(lesson_ids) or any(headings.count(item) != 1 for item in lesson_ids):
            raise CourseCatalogError("Lesson IDs must be unique and match one Markdown heading each")
        return CourseDefinition(
            skill.id, skill.name, skill.description, lesson_ids,
            skill.instructions, skill.version_hash,
        )

    def list(self) -> tuple[CourseDefinition, ...]:
        return tuple(self._courses[key] for key in sorted(self._courses))

    def get(self, course_id: str) -> CourseDefinition | None:
        return self._courses.get(course_id)

    def resolve(self, selection: CourseSelection) -> CourseDefinition:
        course = self.get(selection.course_id)
        if course is None or selection.lesson_id not in course.lesson_ids:
            raise CourseSelectionNotFoundError("Course or lesson is not available")
        return course
