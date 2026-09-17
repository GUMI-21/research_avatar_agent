# Project Collaboration Rules

- Plan the overall architecture before implementation, then deliver one coherent change at a time.
- Keep each functional implementation batch around 100 changed lines unless the user explicitly requests a different pace. Documentation changes have no line limit.
- Tests, generated code, repetitive declarations, and comments do not count toward the implementation line guideline. Codex owns adding and running the tests needed for each batch.
- Before editing, explain the goal and affected files. After editing, report test results and pause for user review before starting the next batch.
- At the end of every batch, explicitly state whether any planned code changes still remain.
- Add project-specific interview questions and answers only when the user explicitly requests them; do not generate them automatically. Preserve existing interview notes.
- Communicate concisely in Chinese. Explain unfamiliar Python or FastAPI behavior with common server-side or Go comparisons when useful.
- Add concise comments for Unity lifecycle, coordinate assumptions, and non-obvious logic; avoid comments that only repeat the code.

# Git Workflow

- Keep `main` synchronized with `origin/main` and do milestone work on a dedicated feature branch.
- Use small local commits for each reviewed implementation batch.
- After milestone testing, push the feature branch and use a pull request with squash merge so `main` receives one stage-level commit.
- Do not push or merge unless the user requests it.

# Internship Portfolio Phase

- The active short-term goal is a web-based personal agent workspace suitable for AI Agent internships, with Go backend experience as a secondary candidate strength.
- This workspace is separate from the future avatar teaching-script UI, but it reuses the existing FastAPI service boundary.
- The MVP centers on a usable web workspace for the project's own Personal Agent runtime, LangGraph orchestration, visible run/usage state, and multi-agent handoff in one conversation. The existing text RAG foundation remains available but is not the current delivery priority.
- Treat Codex and Claude as optional specialized worker Agents. Prefer ACP adapters and keep direct CLI adapters only as compatibility fallbacks; the native Personal Agent must run without either CLI.
- Use REST for resource CRUD and WebSocket for AG-UI-compatible streamed run events. Show auditable progress and tool events, never hidden model chain-of-thought.
- Scope every persistent resource by `client_id`. Optimize for a local-first demo with single-digit clients; do not add distributed infrastructure prematurely.
- Resume Obsidian asset relationships, real-Vault tuning, and Context Inspector work after the first usable Agent workflow and frontend are complete. OCR and multimodal retrieval remain optional.
- Keep requested interview notes under `docs/zh/interview/`.

# Research Direction

- Avatar teaching, emotion modeling, and voice are deferred research work; preserve Unity API compatibility. See `docs/zh/research_plan.md` for research and evaluation details.

# Target Architecture

- FastAPI is the central service boundary connecting Unity, web, cloud/local LLM adapters, the emotion model, agent functions, and future voice modules.
- Intended dialogue flow: analyze the user message/dialogue state with the emotion model; send that analysis plus the message to the LLM; analyze the generated reply into final emotion parameters; let Unity render text, expression, scripted motion, and eventually voice.
- The current web client manages agents, sessions, knowledge sources, context, and usage. Teaching-script management remains a later, separate frontend concern.
- LangGraph may orchestrate workspace runs, but FastAPI, repositories, RAG, and runtime adapters remain independent service boundaries.
- The voice module will own speech recognition and speech generation. Unity remains the future 3D/Web/VR presentation client. Do not couple Unity protocols to a specific LLM or emotion model.

# Current Baseline And Priorities

- Use `docs/zh/internship_agent_workspace_plan.md` as the active roadmap; distinguish implemented behavior from target architecture.
- Implemented: workspace persistence and client scoping, native streaming runtime, WebSocket cancellation/replay, usage APIs, Markdown indexing, hybrid retrieval, Agent knowledge-source bindings, and auditable RAG context injection.
- Priority order: LangGraph run orchestration; streamed manual/automatic handoff; then connect the existing Web Shell to real Agent/Session/WebSocket flows. In the first frontend, show the recorded provider, model, token, estimated cost, latency, and error data on each Run/turn and aggregate it in the conversation detail. CC Switch-style time curves and provider/model grouping are a later dashboard enhancement and must not delay a usable workspace.
- After the usable workspace milestone, resume real-Vault RAG validation, Context Inspector detail, note-to-asset persistence, and optional ACP workers. Qdrant and LangGraph are not current runtime dependencies.
- Windows setup and validation commands belong in `server/README.md`. Use `server/.venv/Scripts/python.exe`, apply Alembic migrations before startup, and run the server unittest suite for each backend batch.
- API keys must stay outside Git, documentation, logs, and project memory.
