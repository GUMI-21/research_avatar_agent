"""Public read models for Run usage and observability."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class RunUsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    agent_id: str
    runtime: str
    provider: str | None
    model: str | None
    status: str
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_write_tokens: int | None
    cost_usd: Decimal | None
    cost_status: str
    duration_ms: int | None
    time_to_first_token_ms: int | None
    error_type: str | None
    created_at: datetime


class RecentRunsResponse(BaseModel):
    runs: list[RunUsageRead]


class UsageSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_count: int
    failed_count: int
    unavailable_cost_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: Decimal
    average_duration_ms: int | None
