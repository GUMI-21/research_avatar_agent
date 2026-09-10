"""Agent runtime adapter contracts."""

# 简化外部引用包时的声明
from app.adapters.agent.base import (
    AgentRuntimeAdapter,
    HandoffTarget,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeRequest,
)
from app.adapters.agent.native import NativeAgentRuntime

# 外部引用当前包使用*时对外暴露的类
__all__ = [
    "AgentRuntimeAdapter",
    "HandoffTarget",
    "NativeAgentRuntime",
    "RuntimeEvent",
    "RuntimeEventType",
    "RuntimeRequest",
]
