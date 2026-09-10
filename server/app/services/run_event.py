"""Visibility and persistence policy for normalized Runtime events."""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.agent import RuntimeEvent, RuntimeEventType
from app.models import RunEventRecord
from app.repositories import RunEventRepository
from logs import log


@dataclass(frozen=True)
class EventPolicy:
    # 是否通过websocket实时发送
    stream: bool
    # 是否保存到run_events表
    persist: bool


PUBLIC_DURABLE = EventPolicy(stream=True, persist=True)
PUBLIC_EPHEMERAL = EventPolicy(stream=True, persist=False)
INTERNAL_ONLY = EventPolicy(stream=False, persist=False)

PUBLIC_DURABLE_TYPES = {
    RuntimeEventType.RUN_STARTED,
    RuntimeEventType.RUN_FINISHED,
    RuntimeEventType.RUN_FAILED,
    RuntimeEventType.RUN_CANCELLED,
    RuntimeEventType.AGENT_STARTED,
    RuntimeEventType.AGENT_STATUS,
    RuntimeEventType.RETRIEVAL_STARTED,
    RuntimeEventType.RETRIEVAL_RESULT,
    RuntimeEventType.CONTEXT_PREPARED,
    RuntimeEventType.TOOL_STARTED,
    RuntimeEventType.TOOL_FINISHED,
    RuntimeEventType.HANDOFF_STARTED,
    RuntimeEventType.HANDOFF_FINISHED,
    RuntimeEventType.HANDOFF_REQUESTED,
    RuntimeEventType.USAGE_UPDATED,
    RuntimeEventType.APPROVAL_REQUIRED,
}
# 赋值所有需要持久化的event
EVENT_POLICIES = {
    event_type: PUBLIC_DURABLE for event_type in PUBLIC_DURABLE_TYPES
}
EVENT_POLICIES[RuntimeEventType.ASSISTANT_DELTA] = PUBLIC_EPHEMERAL
EVENT_POLICIES[RuntimeEventType.PROVIDER_RETRY] = INTERNAL_ONLY


class UnsupportedRuntimeEventError(ValueError):
    pass


# run_event逻辑处理
class RunEventService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repository = RunEventRepository(session)

    @staticmethod
    def policy_for(event: RuntimeEvent) -> EventPolicy:
        try:
            return EVENT_POLICIES[event.type]
        except (KeyError, TypeError) as error:
            raise UnsupportedRuntimeEventError(str(event.type)) from error

    async def replay(
        self,
        client_id: str,
        run_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> Sequence[RunEventRecord]:
        return await self._repository.list_events(
            client_id,
            run_id,
            after_sequence=after_sequence,
            limit=limit,
        )

    async def process(
        self,
        client_id: str,
        run_id: str,
        event: RuntimeEvent,
    ) -> RunEventRecord | None:
        policy = self.policy_for(event)
        if not policy.persist:
            # terminal级只打日志
            if not policy.stream:
                log.info(
                    "runtime_event_internal business=agent_run_event "
                    "client_id={} run_id={} event_type={}",
                    client_id,
                    run_id,
                    event.type.value,
                )
            return None
        # 持久化event记入数据库
        record = await self._repository.append(client_id, run_id, event)
        try:
            await self._session.commit()
        except Exception as error:
            await self._session.rollback()
            log.warning(
                "db_mutation_rolled_back table=run_events business=agent_run_event "
                "client_id={} run_id={} event_type={} error_type={}",
                client_id,
                run_id,
                event.type.value,
                type(error).__name__,
            )
            raise
        log.info(
            "db_mutation_committed table=run_events business=agent_run_event "
            "client_id={} run_id={} event_type={} sequence={}",
            client_id,
            run_id,
            record.event_type,
            record.sequence,
        )
        return record
