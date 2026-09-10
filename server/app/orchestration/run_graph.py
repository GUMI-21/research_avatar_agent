"""Minimal LangGraph workflow around provider-neutral Agent runtimes."""

from collections.abc import AsyncIterator
from typing import Literal, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
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


class AgentRunContext(TypedDict):
    """Invocation-only dependencies that must not enter checkpoints."""

    request: RuntimeRequest


# 编排agent状态
class LangGraphRunOrchestrator:
    """Stream Runtime events through a checkpointed LangGraph node."""

    def __init__(
        self,
        runtime: AgentRuntimeAdapter,
        checkpointer: BaseCheckpointSaver[str] | None = None,
    ) -> None:
        # 构建状态图
        self._runtime = runtime
        builder = StateGraph(AgentRunState, context_schema=AgentRunContext)
        builder.add_node("prepare", self._prepare)
        # 转交任务
        builder.add_node("handoff", self._handoff)
        builder.add_node("agent", self._run_agent)
        builder.add_edge(START, "prepare")
        builder.add_conditional_edges("prepare", self._route)
        builder.add_edge("handoff", "agent")
        builder.add_edge("agent", END)
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
    ) -> dict[str, str]:
        payload = {
            "from_agent_id": state["entry_agent_id"],
            "to_agent_id": state["agent_id"],
            "mode": "manual",
        }
        runtime.stream_writer(
            RuntimeEvent(type=RuntimeEventType.HANDOFF_STARTED, payload=payload)
        )
        runtime.stream_writer(
            RuntimeEvent(type=RuntimeEventType.HANDOFF_FINISHED, payload=payload)
        )
        return {"active_agent_id": state["agent_id"], "phase": "handed_off"}

    async def _run_agent(
        self,
        state: AgentRunState,
        runtime: GraphRuntime[AgentRunContext],
    ) -> dict[str, str | None]:
        terminal_event: str | None = None
        request = runtime.context["request"]
        # 调用agent执行接口 逐个获取事件
        async for event in self._runtime.stream(request):
            # LangGraph 当前节点的执行环境，stream_writer 的作用是把节点内部产生的数据发送到 LangGraph 的 custom 流
            runtime.stream_writer(event)
            if event.type in {
                RuntimeEventType.RUN_FINISHED,
                RuntimeEventType.RUN_FAILED,
                RuntimeEventType.RUN_CANCELLED,
            }:
                terminal_event = event.type.value
        return {"phase": "completed", "terminal_event": terminal_event}

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
        }
        config: RunnableConfig = {
            "configurable": {"thread_id": request.run_id}
        }
        context: AgentRunContext = {"request": request}
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
