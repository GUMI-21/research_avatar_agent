# Internship Portfolio Phase: Personal Agent Workspace

## Goal

Deliver a local-first Personal Agent Workspace in roughly 7–9 days. It should be stable enough for an AI Agent internship interview, while demonstrating the candidate's existing backend engineering experience.

The phase focuses on:

- FastAPI, REST resource APIs, and WebSocket run streaming.
- Chinese-first RAG over an Obsidian/Markdown knowledge base.
- A native Personal Agent runtime with LangGraph orchestration and multi-agent handoff.
- Optional Codex and Claude specialized worker Agents behind a unified runtime boundary.
- Inspectable context, citations, usage, cost, latency, and frequency.

Avatar teaching-script UI, Unity, emotion, and voice work are paused during this phase. Existing Unity APIs remain compatible.

## Architecture

```text
React Web
  -> REST CRUD + WebSocket run events
FastAPI
  -> Session/Run Manager
  -> Personal Agent Runtime / LangGraph Orchestrator
  -> Knowledge/RAG Service
  -> Usage and Context Inspector
  -> Runtime Gateway
       -> cloud LLM adapters
       -> ACP adapter for Codex / Claude
       -> direct CLI adapters as fallbacks
SQLite WAL + FTS5 + Qdrant Local vector index
```

Implementation check (2026-09-09): vectors currently live in SQLite with exact
cosine search; Qdrant and WAL configuration are not implemented. Native Agent
runs now use hybrid retrieval over their bound sources and inject cited context
within a 6,000-character budget, with keyword fallback when no Embedding Client
is available. Durable events record the strategy and distinguish candidate
Chunks from the final budgeted selection without storing note text. Real-Vault
validation and the Context Inspector remain planned. Production workspace runs
now use LangGraph; durable checkpoints and automatic handoff are subsequent slices. See the [Server README](../../server/README.md) for
Windows environment setup.

The second LangGraph slice routes production runs through the graph. The third
adds an explicit `target_agent_id`; runs targeting another Agent follow
`prepare -> handoff -> agent` and persist replayable handoff events. The shared
in-memory checkpointer stores metadata without messages, prompts, or RAG text.
Durable checkpoints, the frontend `@agent` picker, and restricted automatic
handoff remain subsequent slices.

FastAPI remains the service boundary. LangGraph coordinates state transitions within a run; it does not own APIs, repositories, file scanning, or subprocess lifecycle.

## Protocols

REST owns Agent, Session, Knowledge Source, Usage, and demo-client resource operations.

WebSocket owns long-running turns using AG-UI-compatible events plus project-specific context, handoff, and usage events:

```text
run_started
retrieval_started / retrieval_result
context_prepared
agent_started / agent_status
assistant_delta
tool_started / tool_finished
handoff_started / handoff_finished
usage_updated
run_finished / run_failed
```

The UI shows auditable progress and tool activity, not hidden model chain-of-thought. Provider-supported reasoning summaries, if used, are labeled separately.

## Client Isolation

Agents, sessions, messages, runs, delegations, knowledge data, and usage events all carry `client_id`. Repository methods require client scope even when a resource ID is known.

The demo targets single-digit clients with one FastAPI process, SQLite WAL, and an in-process run manager. Redis, distributed queues, and orchestration infrastructure are out of scope.

A future public demo uses a restricted client with seed data, quotas, and no access to local paths or dangerous CLI tools.

## Obsidian RAG

The importer supports Markdown, frontmatter, wiki links, `![[asset.png]]`, and standard Markdown images. The MVP preserves note-to-asset relationships and safely previews assets inside the Vault boundary.

OCR, image embeddings, and multimodal retrieval follow after text RAG is stable.

Retrieval combines keyword and vector results, applies client/source filters, deduplicates chunks, and builds cited context. The current local default is FastEmbed multilingual MiniLM; evaluate retrieval quality on real notes on Windows/macOS before changing models.

## Multi-Agent Model

- The native Personal Agent owns intent analysis, retrieval, context assembly, routing, and final synthesis, and remains usable without Codex or Claude.
- An Agent stores prompt, runtime, model, tools, and knowledge scope.
- A Session has one entry Agent, while each Message records its actual `agent_id`.
- A Delegation records the parent run, target Agent, task, status, and result.
- Users may hand off with `@agent-name`; Agents may use a controlled delegation tool.
- Subagents receive a task summary and selected context instead of a full parent transcript.
- MVP delegation is streamed, single-chain, cycle-checked, and limited to depth two.

## Delivery Batches

1. Architecture, collaboration rules, and an on-demand interview-review process.
2. SQLite migrations, client isolation, Agent/Session/Message repositories and APIs.
3. React shell and WebSocket Mock Chat vertical slice.
4. Obsidian import, Chinese hybrid RAG, citations, and Context Inspector.
5. LangGraph runs, checkpoints, traces, and streamed manual/automatic handoff. This is the current priority.
6. Connect the Web Shell to real Agent/Session CRUD, message history, WebSocket runs, cancellation, reconnect, and handoff. Show provider, model, tokens, estimated cost, latency, and errors on each Run/turn and aggregate Runs in the conversation detail.
7. Finish restricted demo mode, documentation, tests, and interview packaging. If the core workflow is ready, add a dashboard based on the [CC Switch statistics hierarchy](https://cc-switch.dev/docs/local-routing/usage-statistics/), with time/provider/model filters, summary cards, trends, and run details; these aggregate charts do not block the first usable workspace.
8. After the interview-ready workspace, resume real-Vault RAG tuning, full Context Inspector and asset previews, then optional ACP/Codex/Claude workers and multimodal retrieval.

Each batch contains about 100 lines of core implementation, is tested independently, and pauses for review.

## Completion Criteria

- A clean environment starts from the README.
- Agents and sessions survive restart.
- WebSocket events and assistant text stream reliably.
- The existing text RAG path does not block the first interview-ready workspace; real-Vault tuning follows that milestone.
- The native Personal Agent retrieves, orchestrates, and answers without requiring Codex or Claude.
- Tasks move between Agents in one visible conversation.
- Codex and Claude real-runtime checks do not block the native Personal Agent release.
- Resource IDs cannot bypass client isolation.
- One run exposes context, model, usage, cost status, and latency.
- A repeatable two-minute demo is available, with project interview Q&A generated on request.
