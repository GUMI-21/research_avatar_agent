"""Minimal LangGraph workflow around provider-neutral Agent runtimes."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from typing import Literal, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, StateGraph
from langgraph.runtime import Runtime as GraphRuntime

from app.adapters.agent import (
    AgentRuntimeAdapter,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeRequest,
)


class AgentRunState(TypedDict):
    """Serializable state saved at each graph step."""

    run_id: str
    client_id: str
    agent_id: str
    session_id: str
    entry_agent_id: str
    active_agent_id: str
    phase: str
    terminal_event: str | None
    pending_agent_id: str | None
    handoff_depth: int
    visited_agent_ids: list[str]


@dataclass(frozen=True)
class AgentRunTarget:
    runtime: AgentRuntimeAdapter
    request: RuntimeRequest


@dataclass
class AgentRunInvocation:
    runtime: AgentRuntimeAdapter
    request: RuntimeRequest
    targets: dict[str, AgentRunTarget]
    pending_summary: str = ""
    pending_mode: str = "manual"


class AgentRunContext(TypedDict):
    """Invocation-only dependencies that must not enter checkpoints."""

    invocation: AgentRunInvocation


class HandoffRoutingError(RuntimeError):
    pass


# 编排agent状态
class LangGraphRunOrchestrator:
    """Stream Runtime events through a checkpointed LangGraph node."""

    def __init__(
        self,
        runtime: AgentRuntimeAdapter,
        checkpointer: BaseCheckpointSaver[str] | None = None,
        handoff_targets: dict[str, AgentRunTarget] | None = None,
    ) -> None:
        # 构建状态图
        self._runtime = runtime
        self._handoff_targets = handoff_targets or {}
        builder = StateGraph(AgentRunState, context_schema=AgentRunContext)
        builder.add_node("prepare", self._prepare)
        # 转交任务
        builder.add_node("handoff", self._handoff)
        builder.add_node("agent", self._run_agent)
        builder.add_edge(START, "prepare")
        builder.add_conditional_edges("prepare", self._route)
        builder.add_edge("handoff", "agent")
        builder.add_conditional_edges("agent", self._after_agent)
        self._graph = builder.compile(
            checkpointer=checkpointer or InMemorySaver(),
            name="personal_agent_run",
        )

    @staticmethod
    async def _prepare(state: AgentRunState) -> dict[str, str]:
        return {"phase": "ready"}

    @staticmethod
    def _route(state: AgentRunState) -> Literal["handoff", "agent"]:
        return (
            "handoff"
            if state["entry_agent_id"] != state["agent_id"]
            else "agent"
        )

    # 转交任务
    @staticmethod
    async def _handoff(
        state: AgentRunState,
        runtime: GraphRuntime[AgentRunContext],
    ) -> dict[str, object]:
        invocation = runtime.context["invocation"]
        target_id = state["pending_agent_id"]
        if target_id is None:
            raise HandoffRoutingError("Missing handoff target")
        depth = state["handoff_depth"]
        if invocation.pending_mode == "automatic":
            if depth >= 2 or target_id in state["visited_agent_ids"]:
                raise HandoffRoutingError("Handoff depth or cycle rejected")
            target = invocation.targets.get(target_id)
            if target is None:
                raise HandoffRoutingError("Handoff target unavailable")
            invocation.runtime = target.runtime
            visited_ids = {*state["visited_agent_ids"], target_id}
            invocation.request = replace(
                target.request,
                message=invocation.pending_summary,
                handoff_targets=(
                    tuple(
                        item for item in target.request.handoff_targets
                        if item.agent_id not in visited_ids
                    )
                    if depth + 1 < 2 else ()
                ),
            )
            depth += 1
        payload = {
            "from_agent_id": state["active_agent_id"],
            "to_agent_id": target_id,
            "mode": invocation.pending_mode,
        }
        runtime.stream_writer(
            RuntimeEvent(type=RuntimeEventType.HANDOFF_STARTED, payload=payload)
        )
        runtime.stream_writer(
            RuntimeEvent(type=RuntimeEventType.HANDOFF_FINISHED, payload=payload)
        )
        return {
            "active_agent_id": target_id,
            "phase": "handed_off",
            "pending_agent_id": None,
            "handoff_depth": depth,
            "visited_agent_ids": [*state["visited_agent_ids"], target_id],
        }

    async def _run_agent(
        self,
        state: AgentRunState,
        runtime: GraphRuntime[AgentRunContext],
    ) -> dict[str, str | None]:
        terminal_event: str | None = None
        invocation = runtime.context["invocation"]
        # 调用agent执行接口 逐个获取事件
        pending_agent_id: str | None = None
        async for event in invocation.runtime.stream(invocation.request):
            # LangGraph 当前节点的执行环境，stream_writer 的作用是把节点内部产生的数据发送到 LangGraph 的 custom 流
            runtime.stream_writer(event)
            if event.type in {
                RuntimeEventType.RUN_FINISHED,
                RuntimeEventType.RUN_FAILED,
                RuntimeEventType.RUN_CANCELLED,
            }:
                terminal_event = event.type.value
            if event.type is RuntimeEventType.HANDOFF_REQUESTED:
                target_id = event.payload.get("to_agent_id")
                summary = event.payload.get("task_summary")
                if isinstance(target_id, str) and isinstance(summary, str):
                    pending_agent_id = target_id
                    invocation.pending_summary = summary
                    invocation.pending_mode = "automatic"
        return {
            "phase": "handoff_requested" if pending_agent_id else "completed",
            "terminal_event": terminal_event,
            "pending_agent_id": pending_agent_id,
        }

    @staticmethod
    def _after_agent(state: AgentRunState) -> Literal["handoff", "__end__"]:
        return "handoff" if state["pending_agent_id"] else "__end__"

    async def stream(
        self,
        request: RuntimeRequest,
        *,
        entry_agent_id: str | None = None,
    ) -> AsyncIterator[RuntimeEvent]:
        entry_agent_id = entry_agent_id or request.agent_id
        initial: AgentRunState = {
            "run_id": request.run_id,
            "client_id": request.client_id,
            "agent_id": request.agent_id,
            "session_id": request.session_id,
            "entry_agent_id": entry_agent_id,
            "active_agent_id": entry_agent_id,
            "phase": "pending",
            "terminal_event": None,
            "pending_agent_id": (
                request.agent_id if entry_agent_id != request.agent_id else None
            ),
            "handoff_depth": 0,
            "visited_agent_ids": [entry_agent_id],
        }
        config: RunnableConfig = {
            "configurable": {"thread_id": request.run_id}
        }
        context: AgentRunContext = {
            "invocation": AgentRunInvocation(
                self._runtime, request, self._handoff_targets
            )
        }
        # 根据图开始进入状态流
        async for event in self._graph.astream(
            initial,
            config=config,
            context=context,
            stream_mode="custom",
        ):
            if isinstance(event, RuntimeEvent):
                yield event

    async def get_state(self, run_id: str) -> AgentRunState:
        config: RunnableConfig = {"configurable": {"thread_id": run_id}}
        snapshot = await self._graph.aget_state(config)
        return cast(AgentRunState, snapshot.values)
