"""Provider-neutral contracts for native and external Agent runtimes."""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

'''
runtime 字段       → "native" / "codex"（选择哪种运行方式）
Runtime Protocol   → 规定运行时必须提供什么方法
Runtime 对象       → 实际执行任务的 Adapter 实例
'''
# 自动生成构造函数，frozen: 不可修改内部的值
@dataclass(frozen=True)
class RuntimeRequest:
    run_id: str
    client_id: str
    agent_id: str
    session_id: str
    message: str

# playload：事件执行的具体数据，根据type内容不同；dataclass：自动创建构造函数
@dataclass(frozen=True)
class RuntimeEvent:
    # 前向引用”类型标注
    type: "RuntimeEventType"
    payload: Mapping[str, object] = field(default_factory=dict)


# Agent执行状态类型
class RuntimeEventType(StrEnum):
    """Provider-neutral events exposed to orchestration and WebSocket layers."""

    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    RUN_FAILED = "run_failed"
    RUN_CANCELLED = "run_cancelled"
    AGENT_STARTED = "agent_started"
    AGENT_STATUS = "agent_status"
    RETRIEVAL_STARTED = "retrieval_started"
    RETRIEVAL_RESULT = "retrieval_result"
    TOOL_STARTED = "tool_started"
    TOOL_FINISHED = "tool_finished"
    HANDOFF_STARTED = "handoff_started"
    HANDOFF_FINISHED = "handoff_finished"
    USAGE_UPDATED = "usage_updated"
    ASSISTANT_DELTA = "assistant_delta"
    APPROVAL_REQUIRED = "approval_required"


# 接收RuntimeRequest，产生多个异步RuntimeEvent； ...只声明，不实现
class AgentRuntimeAdapter(Protocol):
    """Stream normalized events without exposing provider-specific output."""

    async def stream(
        self,
        request: RuntimeRequest,
    ) -> AsyncIterator[RuntimeEvent]: ...
