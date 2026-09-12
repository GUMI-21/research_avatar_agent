"""Codex CLI runtime using its non-interactive JSONL protocol."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path

from app.adapters.agent.base import RuntimeEvent, RuntimeEventType, RuntimeRequest

LineSource = Callable[[tuple[str, ...], str], AsyncIterator[str]]


class CodexProcessError(RuntimeError):
    pass


async def _codex_lines(command: tuple[str, ...], prompt: str) -> AsyncIterator[str]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    process.stdin.write(prompt.encode("utf-8"))
    await process.stdin.drain()
    process.stdin.close()
    try:
        async for raw_line in process.stdout:
            yield raw_line.decode("utf-8")
        return_code = await process.wait()
        if return_code:
            raise CodexProcessError(f"Codex exited with status {return_code}")
    finally:
        if process.returncode is None:
            process.terminate()
            await process.wait()


class CodexAgentRuntime:
    """Run Codex inside one configured workspace and normalize public events."""

    def __init__(
        self,
        workspace: Path,
        *,
        executable: str = "codex",
        timeout_seconds: float = 300,
        line_source: LineSource = _codex_lines,
    ) -> None:
        self._workspace = workspace.resolve()
        self._executable = executable
        self._timeout_seconds = timeout_seconds
        self._line_source = line_source

    def _command(self, model: str | None) -> tuple[str, ...]:
        command = [
            self._executable, "exec", "--json", "--ephemeral",
            "--sandbox", "workspace-write", "--approve-for-me",
            "--cd", str(self._workspace),
        ]
        if model:
            command.extend(("--model", model))
        command.append("-")
        return tuple(command)

    @staticmethod
    def _prompt(request: RuntimeRequest) -> str:
        sections = [
            ("Agent instructions", request.system_prompt),
            ("Recent conversation", request.conversation_context),
            ("Long-term memory", request.memory_context),
            ("Task", request.message),
        ]
        return "\n\n".join(
            f"## {title}\n{content.strip()}"
            for title, content in sections if content.strip()
        )

    async def stream(self, request: RuntimeRequest) -> AsyncIterator[RuntimeEvent]:
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        yield RuntimeEvent(
            type=RuntimeEventType.AGENT_STARTED,
            payload={"agent_id": request.agent_id, "runtime": "codex"},
        )
        completed = False
        try:
            async with asyncio.timeout(self._timeout_seconds):
                async for line in self._line_source(
                    self._command(request.model), self._prompt(request)
                ):
                    event = json.loads(line)
                    if event.get("type") == "item.completed":
                        item = event.get("item", {})
                        if item.get("type") == "agent_message" and item.get("text"):
                            yield RuntimeEvent(
                                type=RuntimeEventType.ASSISTANT_DELTA,
                                payload={"text": item["text"]},
                            )
                    elif event.get("type") == "turn.completed":
                        usage = event.get("usage", {})
                        yield RuntimeEvent(
                            type=RuntimeEventType.USAGE_UPDATED,
                            payload={
                                "provider": "codex",
                                "model": request.model,
                                "input_tokens": usage.get("input_tokens"),
                                "output_tokens": usage.get("output_tokens"),
                                "cache_read_tokens": usage.get("cached_input_tokens"),
                                "usage_status": "reported" if usage else "unavailable",
                                "cost_status": "unavailable",
                            },
                        )
                        completed = True
            if not completed:
                raise CodexProcessError("Codex stream ended before turn.completed")
        except Exception as error:
            yield RuntimeEvent(
                type=RuntimeEventType.RUN_FAILED,
                payload={"error_type": type(error).__name__},
            )
            raise
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)
