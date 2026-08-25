"""Registry for replaceable Agent runtime adapters."""

from collections.abc import Callable

from app.adapters.agent import AgentRuntimeAdapter

# Callable[参数, 返回类型]
RuntimeFactory = Callable[[], AgentRuntimeAdapter]


class RuntimeNotFoundError(LookupError):
    pass


class RuntimeAlreadyRegisteredError(ValueError):
    pass

# 本质是一个runtime_id : runtimeAdapter字典
class RuntimeRegistry:
    def __init__(self) -> None:
        self._factories: dict[str, RuntimeFactory] = {}

    # runtime_id：执行器标识
    def register(self, runtime_id: str, factory: RuntimeFactory) -> None:
        if runtime_id in self._factories:
            raise RuntimeAlreadyRegisteredError(runtime_id)
        self._factories[runtime_id] = factory

    # 创建AgentRuntimeAdapter
    def create(self, runtime_id: str) -> AgentRuntimeAdapter:
        try:
            factory = self._factories[runtime_id]
        except KeyError as error:
            raise RuntimeNotFoundError(runtime_id) from error
        return factory()

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._factories))
