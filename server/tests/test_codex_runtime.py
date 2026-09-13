"""Tests for Codex CLI JSONL event normalization."""

import json
import unittest
from collections.abc import AsyncIterator
from pathlib import Path

from app.adapters.agent import CodexAgentRuntime, RuntimeEventType, RuntimeRequest


def request(
    model: str | None = None, runtime_thread_id: str | None = None
) -> RuntimeRequest:
    return RuntimeRequest(
        run_id="run-1", client_id="alice", agent_id="coder",
        session_id="session-1", message="Implement feature",
        model=model, runtime_thread_id=runtime_thread_id,
        system_prompt="Follow AGENTS.md",
    )


class CodexRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_builds_safe_command_and_normalizes_result(self) -> None:
        captured: dict[str, object] = {}

        async def lines(command: tuple[str, ...], prompt: str) -> AsyncIterator[str]:
            captured.update(command=command, prompt=prompt)
            yield json.dumps({
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "Done"},
            })
            yield json.dumps({
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 21,
                    "cached_input_tokens": 8,
                    "output_tokens": 4,
                },
            })

        runtime = CodexAgentRuntime(
            Path("project"), executable="codex-test", line_source=lines
        )
        events = [event async for event in runtime.stream(request())]

        command = captured["command"]
        self.assertEqual(command[0:3], ("codex-test", "exec", "--json"))
        self.assertIn("--approve-for-me", command)
        self.assertNotIn("--sandbox", command)
        self.assertNotIn("--ephemeral", command)
        self.assertNotIn("--model", command)
        self.assertIn("## Task\nImplement feature", captured["prompt"])
        self.assertEqual(events[2].payload, {"text": "Done"})
        self.assertEqual(events[3].payload["cache_read_tokens"], 8)
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FINISHED)

    async def test_resumes_thread_and_only_sends_current_task(self) -> None:
        captured: dict[str, object] = {}

        async def lines(command: tuple[str, ...], prompt: str) -> AsyncIterator[str]:
            captured.update(command=command, prompt=prompt)
            yield json.dumps({"type": "thread.started", "thread_id": "thread-1"})
            yield json.dumps({"type": "turn.completed", "usage": {}})

        runtime = CodexAgentRuntime(Path("project"), line_source=lines)
        events = [
            event async for event in runtime.stream(
                request(runtime_thread_id="thread-1")
            )
        ]

        self.assertEqual(
            captured["command"][-3:], ("resume", "thread-1", "-")
        )
        self.assertEqual(
            str(captured["prompt"]).splitlines(),
            ["## Task", "Implement feature"],
        )
        self.assertEqual(events[2].payload["thread_id"], "thread-1")
    async def test_maps_safe_tool_metadata_without_command_or_arguments(self) -> None:
        async def lines(command: tuple[str, ...], prompt: str) -> AsyncIterator[str]:
            items = [
                {"type": "item.started", "item": {
                    "id": "1", "type": "command_execution", "command": "secret",
                }},
                {"type": "item.completed", "item": {
                    "id": "1", "type": "command_execution",
                    "command": "secret", "exit_code": 0,
                }},
                {"type": "item.started", "item": {
                    "id": "2", "type": "mcp_tool_call", "server": "mail",
                    "tool": "search", "arguments": {"token": "secret"},
                }},
                {"type": "item.completed", "item": {
                    "id": "3", "type": "file_change",
                    "changes": [{"path": "app.py", "kind": "update"}],
                }},
                {"type": "turn.completed", "usage": {}},
            ]
            for item in items:
                yield json.dumps(item)

        events = [
            event async for event in CodexAgentRuntime(
                Path("project"), line_source=lines
            ).stream(request())
        ]

        self.assertEqual(events[2].type, RuntimeEventType.TOOL_STARTED)
        self.assertEqual(events[3].payload["exit_code"], 0)
        self.assertNotIn("command", events[3].payload)
        self.assertEqual(events[4].payload["tool_name"], "search")
        self.assertNotIn("arguments", events[4].payload)
        self.assertEqual(
            events[5].payload["changes"],
            [{"path": "app.py", "kind": "update"}],
        )

    async def test_model_override_and_incomplete_stream_fail(self) -> None:
        async def lines(command: tuple[str, ...], prompt: str) -> AsyncIterator[str]:
            self.assertEqual(command[-3:], ("--model", "gpt-test", "-"))
            if False:
                yield ""

        runtime = CodexAgentRuntime(Path("project"), line_source=lines)
        events = []
        with self.assertRaises(Exception):
            async for event in runtime.stream(request("gpt-test")):
                events.append(event)
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FAILED)

    async def test_retry_is_public_but_provider_error_text_is_not(self) -> None:
        async def lines(command: tuple[str, ...], prompt: str) -> AsyncIterator[str]:
            yield json.dumps({"type": "error", "message": "private detail"})
            yield json.dumps({"type": "turn.failed", "error": {"message": "secret"}})

        events = []
        with self.assertRaises(Exception):
            async for event in CodexAgentRuntime(
                Path("project"), line_source=lines
            ).stream(request()):
                events.append(event)

        self.assertEqual(events[-2].type, RuntimeEventType.PROVIDER_RETRY)
        self.assertNotIn("message", events[-2].payload)
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FAILED)


if __name__ == "__main__":
    unittest.main()
