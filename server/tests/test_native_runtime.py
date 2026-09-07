"""Tests for the API-backed native Personal Agent runtime."""

import unittest
from collections.abc import AsyncIterator

from app.adapters.agent import NativeAgentRuntime, RuntimeEventType, RuntimeRequest
from app.adapters.llm import (
    LLMClient,
    LLMRequest,
    LLMResult,
    LLMStreamChunk,
    LLMUsage,
)
from app.schemas.llm import LLMProvider


class FakeLLMClient(LLMClient):
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.last_request: LLMRequest | None = None

    async def generate(self, request: LLMRequest) -> LLMResult:
        self.last_request = request
        if self.error is not None:
            raise self.error
        return LLMResult(
            text=f"Reply: {request.message}",
            provider=LLMProvider.MOCK,
            model="mock-echo",
        )


class ChunkedLLMClient(FakeLLMClient):
    async def stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        for text in ("Reply: ", request.message):
            yield LLMStreamChunk(
                text=text,
                provider=LLMProvider.MOCK,
                model="mock-stream",
            )
        yield LLMStreamChunk(
            text="",
            provider=LLMProvider.MOCK,
            model="mock-stream",
            usage=LLMUsage(input_tokens=5, output_tokens=2),
        )


def make_request(knowledge_context: str = "") -> RuntimeRequest:
    return RuntimeRequest(
        run_id="run-1",
        client_id="client-a",
        agent_id="agent-1",
        session_id="session-1",
        message="Hello",
        system_prompt="You are a personal assistant.",
        knowledge_context=knowledge_context,
    )


class NativeAgentRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_success_is_normalized_to_runtime_events(self) -> None:
        client = FakeLLMClient()
        runtime = NativeAgentRuntime(client)

        events = [
            event
            async for event in runtime.stream(
                make_request("<knowledge_context>Notes</knowledge_context>")
            )
        ]

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
        self.assertIn("用户问题:\nHello", events[2].payload["text"])
        self.assertEqual(events[3].payload["cost_status"], "unavailable")
        assert client.last_request is not None
        self.assertEqual(
            client.last_request.instructions,
            "You are a personal assistant.",
        )
        self.assertEqual(
            client.last_request.message,
            "<knowledge_context>Notes</knowledge_context>\n\n用户问题:\nHello",
        )

    async def test_stream_chunks_become_separate_assistant_deltas(self) -> None:
        runtime = NativeAgentRuntime(ChunkedLLMClient())

        events = [event async for event in runtime.stream(make_request())]
        deltas = [
            event.payload["text"]
            for event in events
            if event.type is RuntimeEventType.ASSISTANT_DELTA
        ]

        self.assertEqual(deltas, ["Reply: ", "Hello"])
        self.assertEqual(events[-2].payload["model"], "mock-stream")
        self.assertEqual(events[-2].payload["input_tokens"], 5)
        self.assertEqual(events[-2].payload["output_tokens"], 2)
        self.assertEqual(events[-2].payload["usage_status"], "reported")

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
