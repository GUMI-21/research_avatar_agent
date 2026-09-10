"""Coordinate one Agent Run from runtime selection to streamed events."""

import asyncio
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, replace
from hashlib import sha256
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.adapters.agent import (
    HandoffTarget,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeRequest,
)
from app.adapters.knowledge import EmbeddingClient
from app.models import MessageRecord
from app.orchestration import AgentRunTarget, LangGraphRunOrchestrator
from app.repositories import AgentRepository, MessageRepository, SessionRepository
from app.services.message import MessageService
from app.services.knowledge_context import (
    KnowledgeContextResult,
    assemble_knowledge_context,
)
from app.services.knowledge_retrieval import KnowledgeRetrievalService
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
KNOWLEDGE_PER_SOURCE_LIMIT = 5
KNOWLEDGE_CONTEXT_BUDGET_CHARS = 6000
# 注入最近 12 条、最多 6000 字符的短期会话上下文；装配同客户端 handoff 候选。
RECENT_MESSAGE_LIMIT = 12
RECENT_CONTEXT_BUDGET_CHARS = 6000


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_token_count(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((perf_counter() - started_at) * 1000))


# 装配短期上下文
def _assemble_recent_context(messages: Sequence[MessageRecord]) -> str:
    selected: list[str] = []
    remaining = RECENT_CONTEXT_BUDGET_CHARS
    for item in reversed(messages):
        prefix = f"{item.role}: "
        content = item.content.strip()
        if remaining <= len(prefix):
            break
        line = prefix + content[-(remaining - len(prefix)):]
        selected.append(line)
        remaining -= len(line) + 1
        if len(line) < len(prefix) + len(content):
            break
    return "\n".join(reversed(selected))


def _context_prepared_event(
    context: KnowledgeContextResult,
    strategy: str,
) -> RuntimeEvent:
    return RuntimeEvent(
        type=RuntimeEventType.CONTEXT_PREPARED,
        payload={
            "included_chunk_ids": list(context.included_chunk_ids),
            "used_chars": context.used_chars,
            "budget_chars": context.budget_chars,
            "truncated": context.truncated,
            "retrieval_strategy": strategy,
            "context_sha256": sha256(
                context.text.encode("utf-8")
            ).hexdigest(),
        },
    )

# 数据类
@dataclass(frozen=True)
class StreamedRunEvent:
    run_id: str
    event: RuntimeEvent
    sequence: int | None  # Run 内持久化事件序号，用于重连补发


class RunExecutionParentNotFoundError(LookupError):
    pass


class RuntimeEndedWithoutTerminalEventError(RuntimeError):
    pass


# Agent Run 执行与事件编排服务
class RunExecutionService:
    def __init__(
        self,
        session: AsyncSession,
        registry: RuntimeRegistry,
        embedding_client: EmbeddingClient | None = None,
        graph_checkpointer: BaseCheckpointSaver[str] | None = None,
    ) -> None:
        self._session = session
        self._registry = registry
        self._messages = MessageService(session)
        self._runs = RunService(session)
        self._events = RunEventService(session)
        self._retrieval = KnowledgeRetrievalService(session, embedding_client)
        self._retrieval_strategy = "hybrid" if embedding_client else "keyword"
        self._graph_checkpointer = graph_checkpointer

    async def stream(
        self,
        client_id: str,
        session_id: str,
        message: str,
        *,
        target_agent_id: str | None = None,
    ) -> AsyncIterator[StreamedRunEvent]:
        # 对话框
        conversation = await SessionRepository(self._session).get(
            client_id, session_id
        )
        if conversation is None:
            raise RunExecutionParentNotFoundError("Session not found")
        # agent
        entry_agent_id = conversation.agent_id
        agent_repository = AgentRepository(self._session)
        agent = await agent_repository.get(
            client_id, target_agent_id or entry_agent_id
        )
        if agent is None:
            raise RunExecutionParentNotFoundError("Agent not found")
        recent_messages = await MessageRepository(self._session).list_messages(
            client_id, session_id, limit=RECENT_MESSAGE_LIMIT
        )
        available_runtime_ids = set(self._registry.available())
        available_agents = [
            item
            for item in await agent_repository.list_agents(client_id)
            if item.runtime in available_runtime_ids
        ]
        handoff_targets = tuple(
            HandoffTarget(item.id, item.name)
            for item in available_agents
            if item.id != agent.id
        )
        # 根据表中的 runtime 字段调用已注册的 Factory，创建对应 Runtime 实例
        runtime = self._registry.create(agent.runtime)
        # 创建 Agent 执行记录
        run = await self._runs.create_run(
            client_id,
            session_id,
            agent.id,
            runtime=agent.runtime,
            model=agent.model,
        )
        _ = await self._messages.append(
            client_id,
            session_id,
            agent.id,
            role="user",
            content=message,
            run_id=run.id,
        )
        execution_started = perf_counter()
        run_started = await self._process(
            client_id,
            run.id,
            RuntimeEvent(type=RuntimeEventType.RUN_STARTED),
        )
        if run_started is not None:
            yield run_started

        knowledge_context = ""
        try:
            source_ids = (
                sorted(set(agent.knowledge_source_ids))
                if agent.runtime == "native"
                else []
            )
            if source_ids:
                started = await self._process(
                    client_id,
                    run.id,
                    RuntimeEvent(
                        type=RuntimeEventType.RETRIEVAL_STARTED,
                        payload={
                            "source_count": len(source_ids),
                            "strategy": self._retrieval_strategy,
                            "per_source_limit": KNOWLEDGE_PER_SOURCE_LIMIT,
                            "budget_chars": KNOWLEDGE_CONTEXT_BUDGET_CHARS,
                        },
                    ),
                )
                if started is not None:
                    yield started
                hits = []
                for source_id in source_ids:
                    search = (
                        self._retrieval.search_hybrid
                        if self._retrieval_strategy == "hybrid"
                        else self._retrieval.search_keyword
                    )
                    source_hits = await search(
                        client_id, source_id, message,
                        limit=KNOWLEDGE_PER_SOURCE_LIMIT,
                    )
                    hits.extend(source_hits)
                    result = await self._process(
                        client_id,
                        run.id,
                        RuntimeEvent(
                            type=RuntimeEventType.RETRIEVAL_RESULT,
                            payload={
                                "source_id": source_id,
                                "strategy": self._retrieval_strategy,
                                "hit_count": len(source_hits),
                                "chunk_ids": [hit.chunk_id for hit in source_hits],
                                "budget_chars": KNOWLEDGE_CONTEXT_BUDGET_CHARS,
                            },
                        ),
                    )
                    if result is not None:
                        yield result
                # 组装上下文
                context = assemble_knowledge_context(
                    hits, max_chars=KNOWLEDGE_CONTEXT_BUDGET_CHARS
                )
                knowledge_context = context.text
                # 记录截断后的选择；prepared 不代表下游模型已收到或使用这些内容。
                prepared = await self._process(
                    client_id,
                    run.id,
                    _context_prepared_event(context, self._retrieval_strategy),
                )
                if prepared is not None:
                    yield prepared
        except asyncio.CancelledError:
            cancelled = await self._process_terminal(
                client_id, run.id, RuntimeEvent(type=RuntimeEventType.RUN_CANCELLED),
                execution_started,
            )
            if cancelled is not None:
                yield cancelled
            raise
        except Exception as error:
            failure = await self._process_terminal(
                client_id,
                run.id,
                RuntimeEvent(
                    type=RuntimeEventType.RUN_FAILED,
                    payload={"error_type": type(error).__name__},
                ),
                execution_started,
            )
            if failure is not None:
                yield failure
            raise
        # 获取异步迭代器；后续 anext() 才会逐步推进 Agent 执行
        request = RuntimeRequest(
            run_id=run.id,
            client_id=client_id,
            agent_id=agent.id,
            session_id=session_id,
            message=message,
            # 身份、近期会话和 RAG 上下文保持独立边界。
            system_prompt=agent.system_prompt,
            conversation_context=_assemble_recent_context(recent_messages),
            knowledge_context=knowledge_context,
            handoff_targets=handoff_targets,
        )
        graph_targets = {
            item.id: AgentRunTarget(
                self._registry.create(item.runtime),
                replace(
                    request,
                    agent_id=item.id,
                    message="",
                    system_prompt=item.system_prompt,
                    knowledge_context="",
                    handoff_targets=tuple(
                        target for target in handoff_targets
                        if target.agent_id != item.id
                    ) + (HandoffTarget(agent.id, agent.name),),
                ),
            )
            for item in available_agents
            if item.id != agent.id
        }
        orchestrator = LangGraphRunOrchestrator(
            runtime, self._graph_checkpointer, graph_targets
        )
        iterator = orchestrator.stream(
            request,
            entry_agent_id=entry_agent_id,
        )
        terminal_received = False
        assistant_parts: list[str] = []
        assistant_agent_id = agent.id
        time_to_first_token_ms: int | None = None

        while True:
            try:
                event = await anext(iterator)
            except StopAsyncIteration:
                break
            except asyncio.CancelledError:
                if not terminal_received:
                    cancelled = RuntimeEvent(type=RuntimeEventType.RUN_CANCELLED)
                    streamed = await self._process(
                        client_id,
                        run.id,
                        cancelled,
                        duration_ms=_elapsed_ms(execution_started),
                        time_to_first_token_ms=time_to_first_token_ms,
                    )
                    if streamed is not None:
                        yield streamed
                raise
            except Exception as error:
                if not terminal_received:
                    failure = RuntimeEvent(
                        type=RuntimeEventType.RUN_FAILED,
                        payload={"error_type": type(error).__name__},
                    )
                    streamed = await self._process(
                        client_id,
                        run.id,
                        failure,
                        duration_ms=_elapsed_ms(execution_started),
                        time_to_first_token_ms=time_to_first_token_ms,
                    )
                    if streamed is not None:
                        yield streamed
                raise

            terminal_received = event.type in TERMINAL_EVENTS or terminal_received
            if event.type is RuntimeEventType.HANDOFF_FINISHED:
                target_id = event.payload.get("to_agent_id")
                if isinstance(target_id, str):
                    assistant_agent_id = target_id
            if event.type is RuntimeEventType.ASSISTANT_DELTA:
                text = event.payload.get("text")
                if isinstance(text, str):
                    assistant_parts.append(text)
                    if text and time_to_first_token_ms is None:
                        time_to_first_token_ms = _elapsed_ms(execution_started)
            if event.type is RuntimeEventType.RUN_STARTED:
                continue
            duration_ms = (
                _elapsed_ms(execution_started)
                if event.type in TERMINAL_EVENTS
                else None
            )
            streamed = await self._process(
                client_id,
                run.id,
                event,
                duration_ms=duration_ms,
                time_to_first_token_ms=time_to_first_token_ms,
            )
            if event.type is RuntimeEventType.RUN_FINISHED and assistant_parts:
                _ = await self._messages.append(
                    client_id,
                    session_id,
                    assistant_agent_id,
                    role="assistant",
                    content="".join(assistant_parts),
                    run_id=run.id,
                )
            if streamed is not None:
                yield streamed
        # 没有正常结束
        if not terminal_received:
            error = RuntimeEndedWithoutTerminalEventError(run.id)
            failure = RuntimeEvent(
                type=RuntimeEventType.RUN_FAILED,
                payload={"error_type": type(error).__name__},
            )
            streamed = await self._process(
                client_id,
                run.id,
                failure,
                duration_ms=_elapsed_ms(execution_started),
                time_to_first_token_ms=time_to_first_token_ms,
            )
            if streamed is not None:
                yield streamed
            raise error

    async def _process_terminal(
        self,
        client_id: str,
        run_id: str,
        event: RuntimeEvent,
        execution_started: float,
    ) -> StreamedRunEvent | None:
        return await self._process(
            client_id,
            run_id,
            event,
            duration_ms=_elapsed_ms(execution_started),
        )

    async def _process(
        self,
        client_id: str,
        run_id: str,
        event: RuntimeEvent,
        *,
        duration_ms: int | None = None,
        time_to_first_token_ms: int | None = None,
    ) -> StreamedRunEvent | None:
        if event.type in TERMINAL_EVENTS:
            event = RuntimeEvent(
                type=event.type,
                payload={
                    **event.payload,
                    "duration_ms": duration_ms,
                    "time_to_first_token_ms": time_to_first_token_ms,
                },
            )
        status = RUN_EVENT_STATUSES.get(event.type)
        if status is not None:
            await self._runs.transition(
                client_id,
                run_id,
                status,
                error_type=_optional_string(event.payload.get("error_type")),
                duration_ms=duration_ms,
                time_to_first_token_ms=time_to_first_token_ms,
            )
        if event.type is RuntimeEventType.USAGE_UPDATED:
            run = await self._runs.record_usage(
                client_id,
                run_id,
                provider=_optional_string(event.payload.get("provider")),
                model=_optional_string(event.payload.get("model")),
                input_tokens=_optional_token_count(
                    event.payload.get("input_tokens")
                ),
                output_tokens=_optional_token_count(
                    event.payload.get("output_tokens")
                ),
                cache_read_tokens=_optional_token_count(
                    event.payload.get("cache_read_tokens")
                ),
                cache_write_tokens=_optional_token_count(
                    event.payload.get("cache_write_tokens")
                ),
            )
            event = RuntimeEvent(
                type=event.type,
                payload={
                    **event.payload,
                    "cost_usd": str(run.cost_usd) if run.cost_usd is not None else None,
                    "cost_status": run.cost_status,
                },
            )
        policy = self._events.policy_for(event)
        record = await self._events.process(client_id, run_id, event)
        if not policy.stream:
            return None
        return StreamedRunEvent(
            run_id=run_id,
            event=event,
            sequence=record.sequence if record is not None else None,
        )
