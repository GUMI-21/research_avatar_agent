"""Tests for Codex CLI JSONL event normalization."""

import json
import sys
import unittest
from collections.abc import AsyncIterator
from tempfile import TemporaryDirectory
from pathlib import Path

from app.adapters.agent import CodexAgentRuntime, RuntimeEventType, RuntimeRequest
from app.adapters.agent.codex import CodexProcessError, _codex_lines


def request(
    model: str | None = None, runtime_thread_id: str | None = None
) -> RuntimeRequest:
    return RuntimeRequest(
        run_id="run-1", client_id="alice", agent_id="coder",
        session_id="session-1", message="Implement feature",
        model=model, runtime_thread_id=runtime_thread_id,
        system_prompt="Follow AGENTS.md", conversation_context="old turn",
        memory_context="private memory", knowledge_context="retrieved note",
    )


class CodexRuntimeTest(unittest.IsolatedAsyncioTestCase):
    async def test_process_bridge_streams_stdout_and_captures_stderr(self) -> None:
        output = [line async for line in _codex_lines(
            (sys.executable, "-c", "import sys; print(sys.stdin.read().upper())"),
            "hello",
        )]
        self.assertEqual([line.strip() for line in output], ["HELLO"])

        failing = (sys.executable, "-c", "import sys; print('boom', file=sys.stderr); raise SystemExit(3)")
        with self.assertRaisesRegex(CodexProcessError, "status 3: boom"):
            _ = [line async for line in _codex_lines(failing, "")]

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
            Path("."), executable="codex-test", line_source=lines
        )
        events = [event async for event in runtime.stream(request())]

        command = captured["command"]
        self.assertEqual(command[0:3], ("codex-test", "exec", "--json"))
        self.assertIn("--approve-for-me", command)
        self.assertNotIn("--sandbox", command)
        self.assertNotIn("--ephemeral", command)
        self.assertNotIn("--model", command)
        self.assertEqual(captured["prompt"], "Implement feature")
        self.assertEqual(events[2].payload, {"text": "Done"})
        self.assertEqual(events[3].payload["cache_read_tokens"], 8)
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FINISHED)

    async def test_resumes_thread_and_only_sends_current_task(self) -> None:
        captured: dict[str, object] = {}

        async def lines(command: tuple[str, ...], prompt: str) -> AsyncIterator[str]:
            captured.update(command=command, prompt=prompt)
            yield json.dumps({"type": "thread.started", "thread_id": "thread-1"})
            yield json.dumps({"type": "turn.completed", "usage": {}})

        runtime = CodexAgentRuntime(Path("."), line_source=lines)
        events = [
            event async for event in runtime.stream(
                request(runtime_thread_id="thread-1")
            )
        ]

        self.assertEqual(
            captured["command"][-3:], ("resume", "thread-1", "-")
        )
        self.assertEqual(captured["prompt"], "Implement feature")
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
                Path("."), line_source=lines
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

    async def test_workspace_uses_agent_absolute_path_or_default_root(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            child = root / "child"
            child.mkdir()
            runtime = CodexAgentRuntime(root)

            command = runtime._command(None, None, "child")

            self.assertEqual(command[command.index("--cd") + 1], str(child.resolve()))
            external = runtime._command(None, None, str(root.parent))
            self.assertEqual(external[external.index("--cd") + 1], str(root.parent.resolve()))

    async def test_model_override_and_incomplete_stream_fail(self) -> None:
        async def lines(command: tuple[str, ...], prompt: str) -> AsyncIterator[str]:
            self.assertEqual(command[-3:], ("--model", "gpt-test", "-"))
            if False:
                yield ""

        runtime = CodexAgentRuntime(Path("."), line_source=lines)
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
                Path("."), line_source=lines
            ).stream(request()):
                events.append(event)

        self.assertEqual(events[-2].type, RuntimeEventType.PROVIDER_RETRY)
        self.assertNotIn("message", events[-2].payload)
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FAILED)


if __name__ == "__main__":
    unittest.main()
