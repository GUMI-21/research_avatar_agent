"""Discover validated, instruction-only Skills from administrator directories."""

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast, final

import yaml


_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")


class SkillCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    name: str
    description: str
    applicable_scenarios: tuple[str, ...]
    recommended_tools: tuple[str, ...]
    instructions: str
    version_hash: str


@final
class SkillCatalog:
    def __init__(self, directories: tuple[Path, ...], max_file_bytes: int) -> None:
        self._directories = tuple(path.resolve() for path in directories)
        self._max_file_bytes = max_file_bytes
        self._skills: dict[str, SkillDefinition] = {}
        _ = self.refresh()

    def refresh(self) -> tuple[SkillDefinition, ...]:
        discovered: dict[str, SkillDefinition] = {}
        for root in self._directories:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("SKILL.md")):
                resolved = path.resolve()
                if not resolved.is_relative_to(root):
                    raise SkillCatalogError("Skill path escapes its allowed directory")
                skill = self._parse(resolved)
                if skill.id in discovered:
                    raise SkillCatalogError(f"Duplicate Skill id: {skill.id}")
                discovered[skill.id] = skill
        self._skills = discovered
        return self.list()

    def list(self) -> tuple[SkillDefinition, ...]:
        return tuple(self._skills[key] for key in sorted(self._skills))

    def get(self, skill_id: str) -> SkillDefinition | None:
        return self._skills.get(skill_id)

    def _parse(self, path: Path) -> SkillDefinition:
        raw = path.read_bytes()
        if len(raw) > self._max_file_bytes:
            raise SkillCatalogError(f"Skill file is too large: {path.name}")
        try:
            text = raw.decode("utf-8").replace("\r\n", "\n")
        except UnicodeDecodeError as error:
            raise SkillCatalogError("Skill file must be UTF-8") from error
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            raise SkillCatalogError("Skill file must start with YAML frontmatter")
        header_text, instructions = text[4:].split("\n---\n", 1)
        raw_metadata = cast(object, yaml.safe_load(header_text))
        if not isinstance(raw_metadata, dict):
            raise SkillCatalogError("Skill frontmatter must be a mapping")
        metadata = cast(dict[object, object], raw_metadata)
        skill_id = self._text(metadata, "id", 64)
        name = self._text(metadata, "name", 100)
        description = self._text(metadata, "description", 1_000)
        if not _IDENTIFIER.fullmatch(skill_id):
            raise SkillCatalogError("Skill id is invalid")
        scenarios = self._string_list(metadata, "applicable_scenarios", 20)
        tools = self._string_list(metadata, "recommended_tools", 50)
        if any(not _IDENTIFIER.fullmatch(tool) for tool in tools):
            raise SkillCatalogError("Recommended tool name is invalid")
        instructions = instructions.strip()
        if not instructions:
            raise SkillCatalogError("Skill instructions cannot be empty")
        return SkillDefinition(
            skill_id, name, description, scenarios, tools, instructions,
            hashlib.sha256(raw).hexdigest(),
        )

    @staticmethod
    def _text(metadata: dict[object, object], key: str, limit: int) -> str:
        value = metadata.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise SkillCatalogError(f"Skill {key} is invalid")
        return value.strip()

    @staticmethod
    def _string_list(
        metadata: dict[object, object], key: str, limit: int,
    ) -> tuple[str, ...]:
        value = metadata.get(key, [])
        if not isinstance(value, list):
            raise SkillCatalogError(f"Skill {key} is invalid")
        items = cast(list[object], value)
        if len(items) > limit:
            raise SkillCatalogError(f"Skill {key} is invalid")
        normalized: list[str] = []
        for item in items:
            if not isinstance(item, str) or not item.strip():
                raise SkillCatalogError(f"Skill {key} is invalid")
            normalized.append(item.strip())
        return tuple(normalized)
