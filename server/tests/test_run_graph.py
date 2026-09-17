"""Tests for the first LangGraph orchestration boundary."""

import unittest
from collections.abc import AsyncIterator

from app.adapters.agent import RuntimeEvent, RuntimeEventType, RuntimeRequest
from app.orchestration import AgentRunTarget, LangGraphRunOrchestrator
from app.orchestration.run_graph import HandoffRoutingError


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


class DelegatingRuntime:
    def __init__(self, target_id: str, summary: str = "focused task") -> None:
        self.target_id = target_id
        self.summary = summary
        self.request: RuntimeRequest | None = None

    async def stream(
        self, request: RuntimeRequest
    ) -> AsyncIterator[RuntimeEvent]:
        self.request = request
        yield RuntimeEvent(type=RuntimeEventType.RUN_STARTED)
        yield RuntimeEvent(
            type=RuntimeEventType.HANDOFF_REQUESTED,
            payload={
                "from_agent_id": request.agent_id,
                "to_agent_id": self.target_id,
                "task_summary": self.summary,
                "mode": "automatic",
            },
        )


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
        self.assertEqual(state["handoff_depth"], 0)
        self.assertEqual(state["visited_agent_ids"], ["agent-1"])

    async def test_routes_manual_handoff_before_target_runtime(self) -> None:
        request = RuntimeRequest(
            run_id="run-2",
            client_id="client-a",
            agent_id="agent-target",
            session_id="session-1",
            message="delegate",
        )
        orchestrator = LangGraphRunOrchestrator(RecordingRuntime())

        events = [
            event
            async for event in orchestrator.stream(
                request, entry_agent_id="agent-entry"
            )
        ]
        state = await orchestrator.get_state(request.run_id)

        self.assertEqual(
            [event.type for event in events[:2]],
            [RuntimeEventType.HANDOFF_STARTED, RuntimeEventType.HANDOFF_FINISHED],
        )
        self.assertEqual(events[0].payload["from_agent_id"], "agent-entry")
        self.assertEqual(events[0].payload["to_agent_id"], "agent-target")
        self.assertEqual(state["active_agent_id"], "agent-target")

    async def test_automatic_handoff_runs_target_with_summary(self) -> None:
        request = RuntimeRequest(
            "run-3", "client-a", "agent-1", "session-1", "start"
        )
        source = DelegatingRuntime("agent-2", "review this")
        target = RecordingRuntime()
        target_request = RuntimeRequest(
            "run-3", "client-a", "agent-2", "session-1", ""
        )
        orchestrator = LangGraphRunOrchestrator(
            source,
            handoff_targets={
                "agent-2": AgentRunTarget(target, target_request)
            },
        )

        events = [event async for event in orchestrator.stream(request)]
        state = await orchestrator.get_state(request.run_id)

        self.assertEqual(
            [event.type for event in events[1:4]],
            [
                RuntimeEventType.HANDOFF_REQUESTED,
                RuntimeEventType.HANDOFF_STARTED,
                RuntimeEventType.HANDOFF_FINISHED,
            ],
        )
        self.assertEqual(RecordingRuntime.request.message, "review this")
        self.assertEqual(state["active_agent_id"], "agent-2")
        self.assertEqual(state["handoff_depth"], 1)

    async def test_automatic_handoff_rejects_cycle(self) -> None:
        request = RuntimeRequest(
            "run-4", "client-a", "agent-1", "session-1", "start"
        )
        source = DelegatingRuntime("agent-2")
        target = DelegatingRuntime("agent-1")
        orchestrator = LangGraphRunOrchestrator(
            source,
            handoff_targets={
                "agent-2": AgentRunTarget(
                    target,
                    RuntimeRequest(
                        "run-4", "client-a", "agent-2", "session-1", ""
                    ),
                )
            },
        )

        with self.assertRaises(HandoffRoutingError):
            _ = [event async for event in orchestrator.stream(request)]

    async def test_automatic_handoff_rejects_third_delegation(self) -> None:
        request = RuntimeRequest(
            "run-5", "client-a", "agent-1", "session-1", "start"
        )
        runtimes = {
            "agent-2": DelegatingRuntime("agent-3"),
            "agent-3": DelegatingRuntime("agent-4"),
            "agent-4": RecordingRuntime(),
        }
        orchestrator = LangGraphRunOrchestrator(
            DelegatingRuntime("agent-2"),
            handoff_targets={
                agent_id: AgentRunTarget(
                    runtime,
                    RuntimeRequest(
                        "run-5", "client-a", agent_id, "session-1", ""
                    ),
                )
                for agent_id, runtime in runtimes.items()
            },
        )

        with self.assertRaises(HandoffRoutingError):
            _ = [event async for event in orchestrator.stream(request)]


if __name__ == "__main__":
    unittest.main()
