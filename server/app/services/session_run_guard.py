"""Fail-fast Session ownership shared by transports within one server process."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


class SessionRunBusyError(RuntimeError):
    pass


class SessionRunGuard:
    def __init__(self) -> None:
        self._active: set[tuple[str, str]] = set()

    @asynccontextmanager
    async def claim(self, client_id: str, session_id: str) -> AsyncIterator[None]:
        key = (client_id, session_id)
        # 检查和占用之间没有 await；单事件循环内原子，忙碌时不排队执行旧消息。
        if key in self._active:
            raise SessionRunBusyError("Session already has an active Run")
        self._active.add(key)
        try:
            yield
        finally:
            self._active.discard(key)
