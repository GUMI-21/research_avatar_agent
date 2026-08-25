"""Tests for provider-neutral Agent runtime registration."""

import unittest
from collections.abc import AsyncIterator

from app.adapters.agent import RuntimeEvent, RuntimeRequest
from app.services.runtime_registry import (
    RuntimeAlreadyRegisteredError,
    RuntimeNotFoundError,
    RuntimeRegistry,
)


class FakeRuntime:
    async def stream(
        self,
        request: RuntimeRequest,
    ) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(type="assistant_delta", payload={"text": request.message})


class RuntimeRegistryTest(unittest.IsolatedAsyncioTestCase):
    async def test_registered_runtime_is_created_and_streams_events(self) -> None:
        registry = RuntimeRegistry()
        registry.register("native", FakeRuntime)

        runtime = registry.create("native")
        request = RuntimeRequest(
            run_id="run-1",
            client_id="client-a",
            agent_id="agent-1",
            session_id="session-1",
            message="hello",
        )
        events = [event async for event in runtime.stream(request)]

        self.assertEqual(registry.available(), ("native",))
        self.assertEqual(events[0].payload, {"text": "hello"})

    async def test_duplicate_and_unknown_runtime_are_rejected(self) -> None:
        registry = RuntimeRegistry()
        registry.register("native", FakeRuntime)

        with self.assertRaises(RuntimeAlreadyRegisteredError):
            registry.register("native", FakeRuntime)
        with self.assertRaises(RuntimeNotFoundError):
            registry.create("codex")


if __name__ == "__main__":
    unittest.main()
