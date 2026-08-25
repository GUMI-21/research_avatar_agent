"""Provider-neutral contracts for native and external Agent runtimes."""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class RuntimeEvent:
    type: str
    payload: Mapping[str, object] = field(default_factory=dict)


# 接收RuntimeRequest，产生多个异步RuntimeEvent； ...只声明，不实现
class AgentRuntimeAdapter(Protocol):
    """Stream normalized events without exposing provider-specific output."""

    async def stream(
        self,
        request: RuntimeRequest,
    ) -> AsyncIterator[RuntimeEvent]: ...
