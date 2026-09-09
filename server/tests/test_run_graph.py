"""Tests for the first LangGraph orchestration boundary."""

import unittest
from collections.abc import AsyncIterator

from app.adapters.agent import RuntimeEvent, RuntimeEventType, RuntimeRequest
from app.orchestration import LangGraphRunOrchestrator


class RecordingRuntime:
    request: RuntimeRequest | None = None

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        type(self).request = request
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        yield RuntimeEvent(
            type=RuntimeEventType.ASSISTANT_DELTA,
            payload={"text": "hello"},
        )
        yield RuntimeEvent(type=RuntimeEventType.RUN_FINISHED)


class LangGraphRunOrchestratorTest(unittest.IsolatedAsyncioTestCase):
    async def test_streams_runtime_events_and_checkpoints_plain_state(self) -> None:
        request = RuntimeRequest(
            run_id="run-1",
            client_id="client-a",
            agent_id="agent-1",
            session_id="session-1",
            message="hi",
            system_prompt="help",
            knowledge_context="reference",
        )
        orchestrator = LangGraphRunOrchestrator(RecordingRuntime())

        events = [event async for event in orchestrator.stream(request)]
        state = await orchestrator.get_state(request.run_id)

        self.assertEqual(
            [event.type for event in events],
            [
                RuntimeEventType.RUN_STARTED,
                RuntimeEventType.ASSISTANT_DELTA,
                RuntimeEventType.RUN_FINISHED,
            ],
        )
        self.assertEqual(RecordingRuntime.request, request)
        self.assertEqual(state["run_id"], request.run_id)
        self.assertEqual(state["client_id"], request.client_id)
        self.assertEqual(state["active_agent_id"], request.agent_id)
        self.assertEqual(state["phase"], "completed")
        self.assertEqual(state["terminal_event"], "run_finished")
        self.assertNotIn("message", state)
        self.assertNotIn("system_prompt", state)
        self.assertNotIn("knowledge_context", state)
        self.assertTrue(all(
            isinstance(value, (str, type(None))) for value in state.values()
        ))


if __name__ == "__main__":
    unittest.main()
