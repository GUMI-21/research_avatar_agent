"""Client-scoped persistence for auditable Agent Run events."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.agent import RuntimeEvent
from app.models import RunEventRecord, RunRecord
from logs import log


class RunEventRunNotFoundError(LookupError):
    pass


# agent执行状态event记录
class RunEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        client_id: str,
        run_id: str,
        event: RuntimeEvent,
    ) -> RunEventRecord:
        run_statement = select(RunRecord.id).where(
            RunRecord.client_id == client_id,
            RunRecord.id == run_id,
        )
        if (await self._session.execute(run_statement)).scalar_one_or_none() is None:
            raise RunEventRunNotFoundError("Run not found")
        # 计算MAX(sequence) + 1
        sequence_statement = select(
            func.coalesce(func.max(RunEventRecord.sequence), 0) + 1
        ).where(
            RunEventRecord.client_id == client_id,
            RunEventRecord.run_id == run_id,
        )
        sequence = (await self._session.execute(sequence_statement)).scalar_one()
        record = RunEventRecord(
            client_id=client_id,
            run_id=run_id,
            event_type=event.type.value,
            payload=dict(event.payload),
            sequence=sequence,
        )
        self._session.add(record)
        await self._session.flush()
        log.info(
            "db_mutation_staged table=run_events business=agent_run_event "
            "action=create client_id={} run_id={} event_type={} sequence={}",
            client_id,
            run_id,
            record.event_type,
            record.sequence,
        )
        return record

    async def list_events(
        self,
        client_id: str,
        run_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> Sequence[RunEventRecord]:
        statement = (
            select(RunEventRecord)
            .where(
                RunEventRecord.client_id == client_id,
                RunEventRecord.run_id == run_id,
                RunEventRecord.sequence > after_sequence,
            )
            .order_by(RunEventRecord.sequence)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return result.scalars().all()
