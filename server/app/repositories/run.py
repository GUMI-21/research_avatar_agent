"""Client-scoped persistence operations for Agent Runs."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AgentRecord, RunRecord, SessionRecord
from app.models.agent import utc_now
from logs import log


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

    # 设定快找状态
    async def set_status(
        self,
        client_id: str,
        run_id: str,
        status: str,
        *,
        error_type: str | None = None,
        error_message: str | None = None,
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
