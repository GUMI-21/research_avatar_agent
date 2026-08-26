"""Agent runtime adapter contracts."""

# 简化外部引用包时的声明
from app.adapters.agent.base import (
    AgentRuntimeAdapter,
    RuntimeEvent,
    RuntimeEventType,
    RuntimeRequest,
)

# 外部引用当前包使用*时对外暴露的类
__all__ = [
    "AgentRuntimeAdapter",
    "RuntimeEvent",
    "RuntimeEventType",
    "RuntimeRequest",
]
