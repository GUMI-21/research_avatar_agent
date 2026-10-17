# Personal Agent Workspace Roadmap

## Goal

Deliver a stable Native Agent tool loop suitable for an AI Agent internship demo:

> Natural-language task → model selects built-in/MCP tools (optionally guided by
> Skills) → approval when needed → file, browser, mail or calendar operation →
> result → visible audit trail.

Mail/calendar tools and Skills are implemented; real-account integration remains to be validated. Use the Python Agent ecosystem
with clear backend boundaries; existing Go experience is a complementary strength,
not a reason to add another service. Avatar, emotion and voice work is deferred;
keep Unity APIs compatible.

## Implemented baseline

| Area | Current behavior |
| --- | --- |
| Workspace | Persistent Agents, users, Sessions, messages and provider/model settings scoped by client |
| Native runtime | Streaming, multi-turn tool execution, short-term context and managed long-term memory |
| Orchestration | LangGraph, manual/automatic handoff, at most two delegations and cycle rejection |
| Web | REST/WebSocket integration, cancellation, reconnect and durable event replay |
| Codex | CLI proxy adapter, isolated thread binding, project-directory constraints, normalized events and usage |
| Tools and approvals | File listing, UTF-8 reading, Markdown writes, risk levels and approve/reject continuation |
| MCP | Discovery, schema validation, stdio/Streamable HTTP, Playwright integration and URL-domain filtering |
| Google OAuth | State/PKCE authorization, encrypted refresh tokens, connection status and remote revocation |
| Google tools | Automatic access-token refresh; Gmail/Calendar read and write tools guarded by the Registry |
| Skills | `SKILL.md` discovery, per-Agent enablement, Native context injection, Run version records and UI settings |
| Demo mode | Configurable blocking of local and external write-risk tools with a visible UI notice |
| Observability | Runs, tool events, provider/model, tokens, estimated cost, latency and errors |
| Text RAG | Incremental Markdown indexing, FTS5/vector hybrid search, citations, Agent source bindings and context injection |

## Current architecture

```text
React / TypeScript / Vite
  ├─ REST: Agents, Sessions, Memory, Knowledge, configuration, Usage
  └─ WebSocket: replies, handoff, tools, approvals, cancellation, replay
        ↓
FastAPI → Services → Repositories → SQLite
  └─ RunExecutionService / LangGraph
       ├─ Native Runtime → LLM adapters
       │    ├─ short-term context, long-term memory, RAG
       │    └─ Tool Registry → file tools / MCP / Gmail / Calendar
       └─ Codex CLI Adapter → external thread
Google OAuth → encrypted client-scoped credentials → shared API client
```

FastAPI owns the service boundary; LangGraph owns run transitions, not APIs,
repositories or subprocess lifecycle. Native runs do not require Codex/Claude.
Codex receives the current task and manages its own tools, code context and
compaction. ACP/Claude are optional future adapters.

REST manages resources; WebSocket carries AG-UI-compatible run events and project
extensions. Persistent queries require `client_id`. Local usernames and
`X-Client-ID` provide data scope, not authentication. Target single-digit local
clients without distributed infrastructure.

## Known limits

- Checkpoints and pending approvals are in memory. Event replay does not resume execution across processes.
- Automatic handoff has OpenAI wire support; equivalent support for other providers is not assumed.
- Native file tools inherit Server OS permissions, not knowledge-source or Codex directory restrictions.
- MCP filtering checks tool URL arguments, not redirects or all subresources; an empty domain list disables filtering.
- Google tools and Skills are implemented, but the real external flow still needs validation with authorized test accounts.
- Vectors live in SQLite with exact cosine search. Qdrant and WAL configuration are not implemented.
- Restricted demo mode blocks write-risk tools; directory sandboxing, automatic reconnection and complete failure-path acceptance remain pending.
  Missing usage must be labeled honestly; estimates are not billed cost. Audits must exclude credentials,
  full sensitive content and hidden chain-of-thought.

## Priorities

The [Tool/MCP/Skill plan](tool_mcp_skill_plan.md) owns detailed scope and acceptance:

1. Validate Google reads, writes, approvals, revocation and missing scopes with an authorized test account.
2. Validate real MCP disconnection, timeout and frontend status; fix failure paths found.
3. Update startup/architecture docs and demo materials, then complete milestone acceptance.

These are remaining acceptance areas, not a fixed batch count or delivery deadline. Split
implementation into roughly 100 functional lines per reviewed batch; backend and
frontend may be separate batches.

## Retained and deferred work

Retain Markdown heading/line chunking with source lines and hashes, local FastEmbed
multilingual MiniLM, FTS5/vector ranking fused with RRF, budgeted cited context and
keyword fallback without an embedding client. Image references are parsed, but
persistent asset relationships and safe previews remain pending.

Real-Vault evaluation, embedding upgrades, OCR, image relationships, Qdrant, full
Context Inspector, usage charts, ACP/Claude and complex parallel delegation do
not block the current tool loop. See the [research plan](research_plan.md).

## Milestone acceptance

- A clean environment starts using the [Server README](../../server/README.md) and [Web README](../../web/README.md).
- Native runs select tools, request approval, execute, feed results back and answer without external CLI dependencies.
- External writes have no side effects before approval; rejection, timeout, revoked access and MCP disconnection produce recoverable or terminal visible outcomes.
- Resource IDs cannot bypass client scope; Google credentials and results remain isolated.
- One conversation demonstrates handoff and exposes tools, approvals, models, tokens, cost status and latency.
- Backend tests and frontend tests/typecheck/build pass; a repeatable two-minute demo exists.
- Prepare project highlights, tradeoffs and resume wording during closeout; add interview Q&A only on explicit request.
