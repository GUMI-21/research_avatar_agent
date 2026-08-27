"""Tests for the API-backed native Personal Agent runtime."""

import unittest

from app.adapters.agent import NativeAgentRuntime, RuntimeEventType, RuntimeRequest
from app.adapters.llm import LLMClient, LLMRequest, LLMResult
from app.schemas.llm import LLMProvider


class FakeLLMClient(LLMClient):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def generate(self, request: LLMRequest) -> LLMResult:
        if self.error is not None:
            raise self.error
        return LLMResult(
            text=f"Reply: {request.message}",
            provider=LLMProvider.MOCK,
            model="mock-echo",
        )


def make_request() -> RuntimeRequest:
    return RuntimeRequest(
        run_id="run-1",
        client_id="client-a",
        agent_id="agent-1",
        session_id="session-1",
        message="Hello",
    )


class NativeAgentRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_success_is_normalized_to_runtime_events(self) -> None:
        runtime = NativeAgentRuntime(FakeLLMClient())

        events = [event async for event in runtime.stream(make_request())]

        self.assertEqual(
            [event.type for event in events],
            [
                RuntimeEventType.RUN_STARTED,
                RuntimeEventType.AGENT_STARTED,
                RuntimeEventType.ASSISTANT_DELTA,
                RuntimeEventType.USAGE_UPDATED,
                RuntimeEventType.RUN_FINISHED,
            ],
        )
        self.assertEqual(events[2].payload["text"], "Reply: Hello")
        self.assertEqual(events[3].payload["cost_status"], "unavailable")

    async def test_failure_event_is_emitted_before_error_propagates(self) -> None:
        runtime = NativeAgentRuntime(FakeLLMClient(RuntimeError("unavailable")))
        events = []

        with self.assertRaises(RuntimeError):
            async for event in runtime.stream(make_request()):
                events.append(event)

        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FAILED)
        self.assertEqual(events[-1].payload, {"error_type": "RuntimeError"})


if __name__ == "__main__":
    unittest.main()
