"""Public Skill catalog contracts."""

from pydantic import BaseModel


class SkillRead(BaseModel):
    id: str
    name: str
    description: str
    applicable_scenarios: tuple[str, ...]
    recommended_tools: tuple[str, ...]
    version_hash: str


class SkillListResponse(BaseModel):
    skills: list[SkillRead]
