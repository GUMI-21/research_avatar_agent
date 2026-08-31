"""Client-scoped usage and recent Run queries."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import ClientID, DBSession
from app.repositories import RunRepository
from app.schemas.usage import RecentRunsResponse, RunUsageRead, UsageSummaryResponse

router = APIRouter(prefix="/usage")


@router.get("/summary", response_model=UsageSummaryResponse)
async def get_usage_summary(
    client_id: ClientID,
    database_session: DBSession,
) -> UsageSummaryResponse:
    totals = await RunRepository(database_session).summarize_usage(client_id)
    return UsageSummaryResponse.model_validate(totals)


@router.get("/runs", response_model=RecentRunsResponse)
async def list_recent_runs(
    client_id: ClientID,
    database_session: DBSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> RecentRunsResponse:
    runs = await RunRepository(database_session).list_recent(
        client_id,
        limit=limit,
    )
    return RecentRunsResponse(
        runs=[RunUsageRead.model_validate(run) for run in runs]
    )
