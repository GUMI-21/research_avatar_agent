"""Read-only Skill catalog routes."""

from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import ClientID
from app.schemas.skill import SkillListResponse, SkillRead
from app.services.skills import SkillCatalog

router = APIRouter(prefix="/skills")


def get_skill_catalog(request: Request) -> SkillCatalog:
    app_state = request.app.state  # pyright: ignore[reportAny]
    return cast(SkillCatalog, app_state.skill_catalog)


@router.get("", response_model=SkillListResponse)
async def list_skills(
    _client_id: ClientID,
    catalog: Annotated[SkillCatalog, Depends(get_skill_catalog)],
) -> SkillListResponse:
    return SkillListResponse(skills=[
        SkillRead(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            applicable_scenarios=skill.applicable_scenarios,
            recommended_tools=skill.recommended_tools,
            version_hash=skill.version_hash,
        )
        for skill in catalog.list()
    ])
