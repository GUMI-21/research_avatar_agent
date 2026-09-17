"""Tests for the API-backed native Personal Agent runtime."""

import tempfile
import unittest
from pathlib import Path
from collections.abc import AsyncIterator
from dataclasses import replace

from app.adapters.agent import (
    HandoffTarget,
    NativeAgentRuntime,
    RuntimeEventType,
    RuntimeRequest,
)
from app.adapters.agent.native import HandoffRequestRejectedError
from app.adapters.llm import (
    LLMClient,
    LLMRequest,
    LLMResult,
    LLMStreamChunk,
    LLMToolCall,
    LLMUsage,
)
from app.schemas.llm import LLMProvider
from app.tools import ToolApprovalBroker, create_file_tool_registry


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


class ToolCallingLLMClient(FakeLLMClient):
    def __init__(self, target_agent_id: str) -> None:
        super().__init__()
        self.target_agent_id = target_agent_id

    async def stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        self.last_request = request
        yield LLMStreamChunk(
            text="",
            provider=LLMProvider.MOCK,
            model="mock-tools",
            tool_call=LLMToolCall(
                name="delegate_to_agent",
                arguments={
                    "target_agent_id": self.target_agent_id,
                    "task_summary": "Review the implementation",
                },
            ),
        )


class FileToolCallingLLMClient(FakeLLMClient):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[LLMRequest] = []

    async def stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        self.requests.append(request)
        if len(self.requests) == 1:
            yield LLMStreamChunk(
                text="",
                provider=LLMProvider.MOCK,
                model="mock-tools",
                tool_call=LLMToolCall(
                    name="read_text_file",
                    arguments={"path": "README.md", "max_chars": 40},
                ),
            )
            return
        yield LLMStreamChunk(
            text="Read completed",
            provider=LLMProvider.MOCK,
            model="mock-tools",
        )

class WriteToolCallingLLMClient(FakeLLMClient):
    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path
        self.calls = 0

    async def stream(
        self, request: LLMRequest
    ) -> AsyncIterator[LLMStreamChunk]:
        self.calls += 1
        yield LLMStreamChunk(
            text="Done" if self.calls > 1 else "",
            provider=LLMProvider.MOCK,
            model="mock-tools",
            tool_call=None if self.calls > 1 else LLMToolCall(
                name="write_markdown",
                arguments={"path": self.path, "content": "# Approved"},
            ),
        )

def make_request(knowledge_context: str = "") -> RuntimeRequest:
    return RuntimeRequest(
        run_id="run-1",
        client_id="client-a",
        agent_id="agent-1",
        session_id="session-1",
        message="Hello",
        provider="openai",
        model="agent-default-model",
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
        self.assertEqual(client.last_request.client_id, "client-a")
        self.assertEqual(client.last_request.provider, LLMProvider.OPENAI)
        self.assertEqual(client.last_request.model, "agent-default-model")
        self.assertEqual(
            client.last_request.instructions,
            "You are a personal assistant.",
        )
        self.assertEqual(
            client.last_request.message,
            "<knowledge_context>Notes</knowledge_context>\n\n用户问题:\nHello",
        )
        self.assertEqual(client.last_request.tools, ())

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

    async def test_recent_conversation_is_added_before_current_question(self) -> None:
        client = FakeLLMClient()
        runtime = NativeAgentRuntime(client)
        request = replace(
            make_request(),
            conversation_context="user: Earlier\nassistant: Answer",
            memory_context="- Prefer concise Chinese.",
            memory_ids=("memory-1",),
        )

        events = [event async for event in runtime.stream(request)]

        memory_event = next(
            event for event in events
            if event.type is RuntimeEventType.CONTEXT_PREPARED
        )
        self.assertEqual(memory_event.payload["memory_ids"], ["memory-1"])
        assert client.last_request is not None
        self.assertEqual(
            client.last_request.message,
            "近期会话（按时间顺序，仅作上下文）:\n"
            "user: Earlier\nassistant: Answer\n\n"
            "长期记忆（仅作上下文）:\n- Prefer concise Chinese.\n\n"
            "用户问题:\nHello",
        )

    async def test_failure_event_is_emitted_before_error_propagates(self) -> None:
        runtime = NativeAgentRuntime(FakeLLMClient(RuntimeError("unavailable")))
        events = []

        with self.assertRaises(RuntimeError):
            async for event in runtime.stream(make_request()):
                events.append(event)

        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FAILED)
        self.assertEqual(events[-1].payload, {"error_type": "RuntimeError"})

    async def test_allowed_delegate_tool_becomes_handoff_request(self) -> None:
        client = ToolCallingLLMClient("agent-reviewer")
        request = replace(
            make_request(),
            handoff_targets=(HandoffTarget("agent-reviewer", "Reviewer"),),
        )

        events = [event async for event in NativeAgentRuntime(client).stream(request)]

        requested = next(
            event for event in events
            if event.type is RuntimeEventType.HANDOFF_REQUESTED
        )
        self.assertEqual(requested.payload["to_agent_id"], "agent-reviewer")
        self.assertNotIn(
            RuntimeEventType.RUN_FINISHED,
            [event.type for event in events],
        )
        assert client.last_request is not None
        self.assertEqual(client.last_request.tools[0].name, "delegate_to_agent")

    async def test_read_tool_result_is_returned_to_model(self) -> None:
        client = FileToolCallingLLMClient()
        root = Path(__file__).resolve().parents[1]
        runtime = NativeAgentRuntime(client, create_file_tool_registry(root))

        events = [event async for event in runtime.stream(make_request())]

        event_types = [event.type for event in events]
        self.assertIn(RuntimeEventType.TOOL_STARTED, event_types)
        self.assertIn(RuntimeEventType.TOOL_FINISHED, event_types)
        self.assertEqual(len(client.requests), 2)
        self.assertIn("<read_text_file>", client.requests[1].message)
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FINISHED)
    async def test_markdown_write_pauses_for_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "note.md"
            approvals = ToolApprovalBroker()
            runtime = NativeAgentRuntime(
                WriteToolCallingLLMClient(str(path)),
                create_file_tool_registry(),
                approvals,
            )
            events = []
            async for event in runtime.stream(make_request()):
                events.append(event)
                if event.type is RuntimeEventType.APPROVAL_REQUIRED:
                    self.assertFalse(path.exists())
                    approvals.decide(
                        "client-a", "run-1",
                        str(event.payload["approval_id"]), True,
                    )

            self.assertEqual(path.read_text(encoding="utf-8"), "# Approved")
            self.assertIn(RuntimeEventType.TOOL_FINISHED, [item.type for item in events])
    async def test_delegate_tool_rejects_target_outside_allowlist(self) -> None:
        client = ToolCallingLLMClient("agent-unknown")
        request = replace(
            make_request(),
            handoff_targets=(HandoffTarget("agent-reviewer", "Reviewer"),),
        )
        events = []

        with self.assertRaises(HandoffRequestRejectedError):
            async for event in NativeAgentRuntime(client).stream(request):
                events.append(event)

        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FAILED)


if __name__ == "__main__":
    unittest.main()
