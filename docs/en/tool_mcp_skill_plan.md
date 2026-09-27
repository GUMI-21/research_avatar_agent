# Tool, MCP and Skill Plan

See the [Workspace roadmap](internship_agent_workspace_plan.md) for the baseline
and architecture. This document owns Native tool boundaries and remaining
acceptance criteria. Codex manages tools through its external runtime.

Sections 1–4 have code and automated tests; real Google/MCP integration remains
to be validated.

## Responsibilities and execution

- Tool Registry: names, descriptions, schemas, executors, client context and risk.
- MCP Client: map `tools/list` and `tools/call` to the Registry with normalized results/errors.
- Skill: versioned instructions/resources describing when and how to use tools, with no extra execution authority.

```text
Allowed schemas → model selection → Registry approval/validation → execution
  → bounded tool result → model continuation or answer → Run audit
```

Approval and parameter validation must pass before execution. Bound tool steps,
timeouts and result size. External results are untrusted data and cannot change
system instructions, approval policy or tool permissions.

| Risk | Example | Policy |
| --- | --- | --- |
| read_only | Server-accessible local files | Automatic execution allowed |
| local_write | Markdown creation/update | Approval per operation |
| external_read | Browsing, mail/calendar reads | Approval per operation initially |
| external_write | Sending mail, calendar changes, form submissions | Mandatory approval |

File tools currently inherit Server OS permissions; relative paths use the Server
working directory. Do not claim directory sandboxing. Pending approvals are tied
to the current connection/process. URL filtering is not full browser network
isolation. Audit only tool name, risk, status, latency and safe summaries, never
tokens, mail bodies or full file content.

## 1. Google token refresh and API client

- Exchange encrypted, client-scoped refresh tokens for access tokens.
- Share the API client between Gmail and Calendar; isolate credentials and caches by client.
- Distinguish expiration, revocation, insufficient scopes, network errors and refresh failure.
- Keep tokens, authorization responses and mail bodies out of logs and error summaries.

Acceptance: valid refresh credentials allow calls after access-token expiry;
revocation or invalid credentials clearly request reauthorization, without
cross-client reuse. External OAuth restrictions may still require reauthorization.

## 2. Gmail and Calendar read tools

- Add `gmail_list_messages`, `gmail_get_message`, `calendar_list_events`.
- Use official REST APIs through the shared client and Registry as `external_read`.
- Bound query range, pagination/result count and returned content.

Acceptance: requests about today's events or interview-related mail lead to model
tool selection, approval, API execution, result feedback and a final answer.
Rejections and API failures also return through the tool loop. Mail bodies enter
context only as needed, not ordinary logs or audit summaries.

## 3. Gmail and Calendar write tools

- Create drafts, send mail, and create/update/delete calendar events.
- OAuth requests Gmail/Calendar read and write scopes; older connections missing permissions require reauthorization.
- Require approval for every external write. Summaries show recipients, subjects or event times, never credentials.
- Bind approval to client, tool and arguments; retries must not duplicate irreversible side effects.

Acceptance: no external side effects before approval; rejection returns to the
Agent so it can answer. Insufficient permissions, failures and uncertain outcomes
are clearly visible in the UI.

## 4. Skills

Backend and frontend were delivered separately:

- Discover `SKILL.md` in administrator-approved directories with size/reference bounds.
- Parse name, description, applicability and recommended tools; enable per Agent.
- Inject enabled instructions into Native context; record Skill ID and version hash on the Run.
- Show discovered Skills and Agent toggles in settings; show actually loaded Skills in Run details.
- Skills cannot bypass the Registry, approval or Agent permissions and are not separate executors.

Demo candidates: daily work planning (read calendar, organize tasks, create approved
time blocks) and an Obsidian diary assistant (read, organize and approve Markdown changes).

Acceptance: toggles affect context, versions are traceable, and recommended but
unauthorized tools remain blocked by existing permission boundaries.

## 5. Interview demo closeout

- Verify MCP disconnects, timeouts, cancellation and failures cannot leave Runs stuck.
- Surface Tool, MCP, Google and Codex failures in the frontend.
- Restricted demo mode already blocks write-risk tools; validate demo fixtures and real configuration.
- Update architecture/startup docs; prepare a two-minute demo, highlights, tradeoffs and resume wording.
- Run the complete backend unittest suite and frontend tests, typecheck and build.
- Validate real Google/MCP integration with authorized test accounts; mocks do not prove external integration.

Split functional work into roughly 100-line batches as needed; tests, docs and
closeout are exempt. Report results and remaining work, then pause for review.
Do not expand RAG research or automatically generate interview Q&A in this phase.
