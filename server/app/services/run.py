"""Transaction and lifecycle rules for Agent Runs."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm_pricing import estimate_cost_usd
from app.models import RunRecord
from app.repositories import RunRepository
from logs import log

RUN_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"running", "failed", "cancelled"},
    "running": {"completed", "failed", "cancelled"},
    "completed": set(),
    "failed": set(),
    "cancelled": set(),
}


class RunNotFoundError(LookupError):
    pass


class InvalidRunTransitionError(ValueError):
    pass

# agent执行快照逻辑处理
class RunService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = RunRepository(session)

    async def create_run(
        self,
        client_id: str,
        session_id: str,
        agent_id: str,
        *,
        runtime: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> RunRecord:
        run = await self._repository.create(
            client_id,
            session_id,
            agent_id,
            runtime=runtime,
            provider=provider,
            model=model,
        )
        await self._commit("create", run)
        return run

    # 改变状态
    async def transition(
        self,
        client_id: str,
        run_id: str,
        status: str,
        *,
        error_type: str | None = None,
        error_message: str | None = None,
        duration_ms: int | None = None,
        time_to_first_token_ms: int | None = None,
    ) -> RunRecord:
        run = await self._repository.get(client_id, run_id)
        if run is None:
            raise RunNotFoundError(run_id)
        if status not in RUN_TRANSITIONS.get(run.status, set()):
            raise InvalidRunTransitionError(f"{run.status} -> {status}")

        updated = await self._repository.set_status(
            client_id,
            run_id,
            status,
            error_type=error_type,
            error_message=error_message,
            duration_ms=duration_ms,
            time_to_first_token_ms=time_to_first_token_ms,
        )
        if updated is None:
            raise RunNotFoundError(run_id)
        await self._commit("status", updated)
        return updated

    async def record_usage(
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
    ) -> RunRecord:
        cost_usd = estimate_cost_usd(
            provider,
            model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )
        updated = await self._repository.set_usage(
            client_id,
            run_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
            cost_usd=cost_usd,
            cost_status="estimated" if cost_usd is not None else "unavailable",
        )
        if updated is None:
            raise RunNotFoundError(run_id)
        await self._commit("usage", updated)
        return updated

    # services调用repositories数据库的封装方法，如果成功就commit，有错误就rollback
    async def _commit(self, action: str, run: RunRecord) -> None:
        try:
            await self._session.commit()
        except Exception as error:
            await self._session.rollback()
            log.warning(
                "db_mutation_rolled_back table=runs business=agent_run "
                "action={} client_id={} run_id={} error_type={}",
                action,
                run.client_id,
                run.id,
                type(error).__name__,
            )
            raise
        log.info(
            "db_mutation_committed table=runs business=agent_run action={} "
            "client_id={} run_id={} status={}",
            action,
            run.client_id,
            run.id,
            run.status,
        )
