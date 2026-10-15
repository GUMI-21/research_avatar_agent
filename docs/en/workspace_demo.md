# Workspace Demo and Handoff

The Workspace implements conversations, Native execution, LangGraph handoff,
text RAG, memory, tool approvals and Run/Usage inspection. This closeout fixes
obsolete approval cards after terminal events and cross-platform path assertions,
retaining the backend for Avatar integration. Live Google-account validation and
autonomous cloud-model tool selection are deferred, not accepted demo capabilities.

## Startup and validation

The [Server README](../../server/README.md) owns environment, migration, tests and
MCP commands; use the [Web README](../../web/README.md) for the frontend. macOS
uses `.venv/bin/python`; Windows uses `.venv/Scripts/python.exe`. Start both
processes and select a dedicated demo user.

Configure secrets only through local settings or environment variables. Use
public test notes, tool outputs and pages; do not record credentials or private
mail. Label cost estimates and missing usage honestly.

## Key-free infrastructure demo

1. Create a Mock Native Agent and a conversation, send text, and show WebSocket replies and terminal Run state.
2. Inspect message history and Run/Usage, explaining missing tokens and costs.
3. Show Agent, memory, knowledge-source and Skill settings and explain their responsibilities.

This mode demonstrates resources and transport. Mock only echoes; it does not
demonstrate autonomous tool selection, knowledge understanding or memory reasoning.

## Real Native tool demo (model configuration required)

Prepare a tool-capable Native model, a public Markdown fixture with its path, and
optionally Playwright MCP. Rehearse the exact configuration before an approximately
two-minute presentation:

1. Show the Agent model/instructions, ask it to read and summarize the test note, and inspect tool events and the answer.
2. Ask it to write the summary to a test `.md` file. Show approval details, reject first, then approve a new task.
3. Stop another task while approval is pending; verify the cancelled Run and removal of the approval card.
4. Inspect model, tokens, estimated cost and latency; optionally show Agent handoff.

Write demonstrations require writes not to be disabled by Demo mode. Use dedicated
test files. Browser reading can replace the first step and also requires approval.
Cross-process execution recovery is not implemented: disconnection cancels a Run,
and reconnection restores the display of durable events.

## Scope of existing evidence

- Real Playwright MCP and isolated Chrome validated local navigation, snapshots, approval and domain filtering.
- A scripted model plus a real MCP test subprocess validated approval, rejection, timeout, disconnection, cancellation and result feedback.
- Real WebSocket connections validated disconnection cancellation and replay; the actual Web UI validated approval, replies and Usage.
- Full backend unittest and frontend tests/typecheck/build verify the current baseline.

Scripted models and local pages do not prove live-model decisions or third-party
website task quality. Authentication, directory sandboxing, live Google-account
integration and complete external failure-path acceptance remain future work.

## Avatar handoff boundary

Reuse Agents, Sessions, context, Runtime Adapters, LangGraph, tools and auditing.
Keep teaching strategies, student state, emotion estimation and Avatar controls
in independent modules. Unity currently calls the legacy single-turn ChatService
with fixed neutral/idle values; it has not joined the Native pipeline.
Connect Sessions and execution first, then map parameters to VRM expressions,
gaze and actions. See the [Avatar integration plan](avatar_integration_plan.md)
for candidate contracts and research criteria.
