# Project Collaboration Rules

- Plan the overall architecture before implementation, then deliver one coherent change at a time.
- Keep each implementation batch around 300 changed lines unless the user explicitly requests a different pace.
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
- The MVP centers on the project's own Personal Agent runtime and LangGraph orchestration, plus Obsidian/Markdown RAG, visible context and usage management, and multi-agent handoff in one conversation.
- Treat Codex and Claude as optional specialized worker Agents. Prefer ACP adapters and keep direct CLI adapters only as compatibility fallbacks; the native Personal Agent must run without either CLI.
- Use REST for resource CRUD and WebSocket for AG-UI-compatible streamed run events. Show auditable progress and tool events, never hidden model chain-of-thought.
- Scope every persistent resource by `client_id`. Optimize for a local-first demo with single-digit clients; do not add distributed infrastructure prematurely.
- Parse Obsidian image embeds and preserve note-to-asset relationships. OCR and multimodal image retrieval are optional after the text RAG path is stable.
- Keep requested interview notes under `docs/zh/interview/`.

# Research Direction

- Working topic: an LLM- and emotion-model-based 3D avatar educational support system.
- Research focus: supplement LLM text with consistent nonverbal expression, including facial expression, gaze, motion, and voice, for a more natural virtual teacher.
- Proposed evaluation compares four conditions: text-only LLM teacher, 3D avatar teacher without an emotion model, 3D avatar teacher with an independent emotion model, and a human teacher.
- Planned evaluation dimensions include learning effectiveness, engagement/presence, and perceived naturalness.

# Target Architecture

- FastAPI is the central service boundary connecting Unity, web, cloud/local LLM adapters, the emotion model, agent functions, and future voice modules.
- Intended dialogue flow: analyze the user message/dialogue state with the emotion model; send that analysis plus the message to the LLM; analyze the generated reply into final emotion parameters; let Unity render text, expression, scripted motion, and eventually voice.
- The current web client manages agents, sessions, knowledge sources, context, and usage. Teaching-script management remains a later, separate frontend concern.
- LangGraph may orchestrate workspace runs, but FastAPI, repositories, RAG, and runtime adapters remain independent service boundaries.
- The voice module will own speech recognition and speech generation. Unity remains the future 3D/Web/VR presentation client. Do not couple Unity protocols to a specific LLM or emotion model.

# Current Baseline And Priorities

- As of the July 21, 2026 presentation baseline, FastAPI exposes `/api/v1/llm/providers`, `/api/v1/llm/config`, and `/api/v1/unity/chat`; Unity loads VRM 1.0 models and calls the Chat API.
- Unity -> Server -> Mock LLM and Server -> Gemini real API have been verified. Direct Unity -> Gemini verification remains a required demo check.
- Near-term order: deliver the agent workspace foundation; add WebSocket chat; integrate Obsidian RAG; add multi-agent handoff and Codex/Claude runtimes; add usage/context inspection; package the interview demo. Resume Unity, emotion, and voice work afterward.
- API keys must stay outside Git, documentation, logs, and project memory.
