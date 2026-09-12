"""Tests for Codex CLI JSONL event normalization."""

import json
import unittest
from collections.abc import AsyncIterator
from pathlib import Path

from app.adapters.agent import CodexAgentRuntime, RuntimeEventType, RuntimeRequest


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
        request = RuntimeRequest(
            run_id="run-1", client_id="alice", agent_id="coder",
            session_id="session-1", message="Implement feature",
            model=None, system_prompt="Follow AGENTS.md",
        )
        events = [event async for event in runtime.stream(request)]

        command = captured["command"]
        self.assertEqual(command[0:3], ("codex-test", "exec", "--json"))
        self.assertNotIn("--model", command)
        self.assertIn("## Task\nImplement feature", captured["prompt"])
        self.assertEqual(events[2].payload, {"text": "Done"})
        self.assertEqual(events[3].payload["cache_read_tokens"], 8)
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FINISHED)

    async def test_model_override_and_incomplete_stream_fail(self) -> None:
        async def lines(command: tuple[str, ...], prompt: str) -> AsyncIterator[str]:
            self.assertEqual(command[-3:], ("--model", "gpt-test", "-"))
            if False:
                yield ""

        runtime = CodexAgentRuntime(Path("project"), line_source=lines)
        request = RuntimeRequest(
            run_id="run-1", client_id="alice", agent_id="coder",
            session_id="session-1", message="work", model="gpt-test",
        )
        events = []
        with self.assertRaises(Exception):
            async for event in runtime.stream(request):
                events.append(event)
        self.assertEqual(events[-1].type, RuntimeEventType.RUN_FAILED)


if __name__ == "__main__":
    unittest.main()
