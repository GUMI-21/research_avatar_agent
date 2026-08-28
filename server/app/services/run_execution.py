"""Coordinate one Agent Run from runtime selection to streamed events."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.agent import RuntimeEvent, RuntimeEventType, RuntimeRequest
from app.repositories import AgentRepository, SessionRepository
from app.services.run import RunService
from app.services.run_event import RunEventService
from app.services.runtime_registry import RuntimeRegistry


RUN_EVENT_STATUSES = {
    RuntimeEventType.RUN_STARTED: "running",
    RuntimeEventType.RUN_FINISHED: "completed",
    RuntimeEventType.RUN_FAILED: "failed",
    RuntimeEventType.RUN_CANCELLED: "cancelled",
}
TERMINAL_EVENTS = {
    RuntimeEventType.RUN_FINISHED,
    RuntimeEventType.RUN_FAILED,
    RuntimeEventType.RUN_CANCELLED,
}

# 数据类
@dataclass(frozen=True)
class StreamedRunEvent:
    run_id: str
    event: RuntimeEvent
    sequence: int | None


class RunExecutionParentNotFoundError(LookupError):
    pass


class RuntimeEndedWithoutTerminalEventError(RuntimeError):
    pass


# agent执行快照生成器
class RunExecutionService:
    def __init__(self, session: AsyncSession, registry: RuntimeRegistry) -> None:
        self._session = session
        self._registry = registry
        self._runs = RunService(session)
        self._events = RunEventService(session)

    async def stream(
        self,
        client_id: str,
        session_id: str,
        message: str,
    ) -> AsyncIterator[StreamedRunEvent]:
        # 对话框
        conversation = await SessionRepository(self._session).get(
            client_id, session_id
        )
        if conversation is None:
            raise RunExecutionParentNotFoundError("Session not found")
        # agent
        agent = await AgentRepository(self._session).get(
            client_id, conversation.agent_id
        )
        if agent is None:
            raise RunExecutionParentNotFoundError("Agent not found")
        # 创建agent执行快照
        run = await self._runs.create_run(
            client_id,
            session_id,
            agent.id,
            runtime=agent.runtime,
            model=agent.model,
        )
        runtime = self._registry.create(agent.runtime)
        # 获取迭代器
        iterator = runtime.stream(
            RuntimeRequest(
                run_id=run.id,
                client_id=client_id,
                agent_id=agent.id,
                session_id=session_id,
                message=message,
            )
        )
        terminal_received = False

        while True:
            try:
                event = await anext(iterator)
            except StopAsyncIteration:
                break
            except Exception as error:
                if not terminal_received:
                    failure = RuntimeEvent(
                        type=RuntimeEventType.RUN_FAILED,
                        payload={"error_type": type(error).__name__},
                    )
                    streamed = await self._process(client_id, run.id, failure)
                    if streamed is not None:
                        yield streamed
                raise

            terminal_received = event.type in TERMINAL_EVENTS or terminal_received
            streamed = await self._process(client_id, run.id, event)
            if streamed is not None:
                yield streamed
        # 没有正常结束
        if not terminal_received:
            error = RuntimeEndedWithoutTerminalEventError(run.id)
            failure = RuntimeEvent(
                type=RuntimeEventType.RUN_FAILED,
                payload={"error_type": type(error).__name__},
            )
            streamed = await self._process(client_id, run.id, failure)
            if streamed is not None:
                yield streamed
            raise error

    async def _process(
        self,
        client_id: str,
        run_id: str,
        event: RuntimeEvent,
    ) -> StreamedRunEvent | None:
        status = RUN_EVENT_STATUSES.get(event.type)
        if status is not None:
            await self._runs.transition(client_id, run_id, status)
        policy = self._events.policy_for(event)
        record = await self._events.process(client_id, run_id, event)
        if not policy.stream:
            return None
        return StreamedRunEvent(
            run_id=run_id,
            event=event,
            sequence=record.sequence if record is not None else None,
        )
