"""Client-scoped persistence operations for Agent Runs."""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRecord, RunRecord, SessionRecord
from app.models.agent import utc_now
from logs import log


@dataclass(frozen=True)
class RunUsageTotals:
    run_count: int
    failed_count: int
    unavailable_cost_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_usd: Decimal
    average_duration_ms: int | None


class RunParentNotFoundError(LookupError):
    def __init__(self, resource: str) -> None:
        self.resource = resource
        super().__init__(f"{resource} not found")


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # 创建agent快照
    async def create(
        self,
        client_id: str,
        session_id: str,
        agent_id: str,
        *,
        runtime: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> RunRecord:
        session_statement = select(SessionRecord.id).where(
            SessionRecord.client_id == client_id,
            SessionRecord.id == session_id,
        )
        if (await self._session.execute(session_statement)).scalar_one_or_none() is None:
            raise RunParentNotFoundError("Session")

        agent_statement = select(AgentRecord.id).where(
            AgentRecord.client_id == client_id,
            AgentRecord.id == agent_id,
        )
        if (await self._session.execute(agent_statement)).scalar_one_or_none() is None:
            raise RunParentNotFoundError("Agent")

        run = RunRecord(
            client_id=client_id,
            session_id=session_id,
            agent_id=agent_id,
            runtime=runtime,
            provider=provider,
            model=model,
        )
        self._session.add(run)
        await self._session.flush()
        log.info(
            "db_mutation_staged table=runs business=agent_run action=create "
            "client_id={} run_id={}",
            client_id,
            run.id,
        )
        return run

    async def get(self, client_id: str, run_id: str) -> RunRecord | None:
        statement = select(RunRecord).where(
            RunRecord.client_id == client_id,
            RunRecord.id == run_id,
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def list_recent(
        self,
        client_id: str,
        *,
        limit: int,
    ) -> Sequence[RunRecord]:
        statement = (
            select(RunRecord)
            .where(RunRecord.client_id == client_id)
            .order_by(RunRecord.created_at.desc())
            .limit(limit)
        )
        return (await self._session.execute(statement)).scalars().all()

    # 统计用量
    async def summarize_usage(self, client_id: str) -> RunUsageTotals:
        statement = select(
            func.count(RunRecord.id).label("run_count"),
            func.sum(case((RunRecord.status == "failed", 1), else_=0)).label(
                "failed_count"
            ),
            func.sum(
                case((RunRecord.cost_status == "unavailable", 1), else_=0)
            ).label("unavailable_cost_count"),
            func.sum(RunRecord.input_tokens).label("input_tokens"),
            func.sum(RunRecord.output_tokens).label("output_tokens"),
            func.sum(RunRecord.cache_read_tokens).label("cache_read_tokens"),
            func.sum(RunRecord.cache_write_tokens).label("cache_write_tokens"),
            func.sum(RunRecord.cost_usd).label("cost_usd"),
            func.avg(RunRecord.duration_ms).label("average_duration_ms"),
        ).where(RunRecord.client_id == client_id)
        row = (await self._session.execute(statement)).one()
        return RunUsageTotals(
            run_count=int(row.run_count or 0),
            failed_count=int(row.failed_count or 0),
            unavailable_cost_count=int(row.unavailable_cost_count or 0),
            input_tokens=int(row.input_tokens or 0),
            output_tokens=int(row.output_tokens or 0),
            cache_read_tokens=int(row.cache_read_tokens or 0),
            cache_write_tokens=int(row.cache_write_tokens or 0),
            cost_usd=Decimal(row.cost_usd or 0).quantize(Decimal("0.000001")),
            average_duration_ms=(
                round(row.average_duration_ms)
                if row.average_duration_ms is not None
                else None
            ),
        )

    # 设定快找状态
    async def set_status(
        self,
        client_id: str,
        run_id: str,
        status: str,
        *,
        error_type: str | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
        time_to_first_token_ms: int | None = None,
    ) -> RunRecord | None:
        run = await self.get(client_id, run_id)
        if run is None:
            return None
        now = utc_now()
        run.status = status
        if status == "running" and run.started_at is None:
            run.started_at = now
        if status in {"completed", "failed", "cancelled"}:
            run.completed_at = now
            run.duration_ms = duration_ms
            run.time_to_first_token_ms = time_to_first_token_ms
        run.error_type = error_type
        run.error_message = error_message
        await self._session.flush()
        log.info(
            "db_mutation_staged table=runs business=agent_run action=status "
            "client_id={} run_id={} status={}",
            client_id,
            run.id,
            status,
        )
        return run

    async def set_usage(
        self,
        client_id: str,
        run_id: str,
        *,
        provider: str | None,
        model: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        cache_read_tokens: int | None,
        cache_write_tokens: int | None,
        cost_usd: Decimal | None,
        cost_status: str,
    ) -> RunRecord | None:
        run = await self.get(client_id, run_id)
        if run is None:
            return None
        if provider is not None:
            run.provider = provider
        if model is not None:
            run.model = model
        run.input_tokens = input_tokens
        run.output_tokens = output_tokens
        run.cache_read_tokens = cache_read_tokens
        run.cache_write_tokens = cache_write_tokens
        run.cost_usd = cost_usd
        run.cost_status = cost_status
        await self._session.flush()
        log.info(
            "db_mutation_staged table=runs business=agent_run action=usage "
            "client_id={} run_id={}",
            client_id,
            run.id,
        )
        return run
