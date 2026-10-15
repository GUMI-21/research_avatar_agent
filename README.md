# Personal Agent Workspace

A local-first AI Agent portfolio project with a React workspace, FastAPI service
boundary, and native runtime orchestrated by LangGraph. The active backend work
is English-led Japanese kana teaching from local course Skills, with validated
model expression suggestions for a future Unity avatar. Legacy Unity APIs remain compatible.

The retained Workspace baseline provides an auditable tool execution loop:

> Natural-language task → model selects tools → approval when required →
> execution → result → visible run and tool audit.

## Current scope

Implemented: workspace conversations, memory, manual/automatic handoff, optional
Codex CLI adapter, file and MCP tools, approval pause/resume, Google OAuth with
token refresh and Gmail/Calendar read/write tools, Agent Skills, Markdown hybrid
RAG, restricted demo mode, and run/usage inspection.

Workspace closeout covers the local engineering baseline, with real isolated
Playwright transport checks and scripted-model tool-loop validation. Live Google
accounts and autonomous cloud-model tool selection remain deferred. After
closeout review, Avatar development reuses the existing backend. Course/output
contracts and optional speech/emotion ports are implemented; runtime course loading
and teaching APIs are next. See the [demo/handoff guide](docs/en/workspace_demo.md) for
the reproducible presentation scope and remaining validation boundaries.

## Repository layout

| Path | Responsibility |
| --- | --- |
| `server/` | FastAPI routes, services, repositories, LangGraph, runtime adapters and tools |
| `web/` | React/TypeScript workspace, conversations, settings and Run/Usage views |
| `courses/` | Local Markdown Skill teaching scripts; English-led Japanese kana is the initial course |
| `avatar-unity/` | Unity/VRM client; further development deferred |
| `shared/` | Reserved for shared contracts and generated types |
| `docs/zh/`, `docs/en/` | Roadmaps and research design |
| `server/docs/` | Backend API and logging reference |

## Start and validate

Follow the [Server README](server/README.md) for configuration, migrations,
backend tests, MCP and OAuth setup, then the [Web README](web/README.md) for
frontend startup, tests and build. Mock chat does not require a cloud API key.
Local client IDs scope data; they are not authentication.

## Documentation

| Topic | 中文 | English |
| --- | --- | --- |
| Current baseline and architecture | [Workspace 路线图](docs/zh/internship_agent_workspace_plan.md) | [Workspace roadmap](docs/en/internship_agent_workspace_plan.md) |
| Next batches and acceptance | [Tool/MCP/Skill 计划](docs/zh/tool_mcp_skill_plan.md) | [Tool/MCP/Skill plan](docs/en/tool_mcp_skill_plan.md) |
| Deferred research | [研究计划](docs/zh/research_plan.md) | [Research plan](docs/en/research_plan.md) |
| Active Avatar backend plan | [Avatar 后端计划](docs/zh/avatar_integration_plan.md) | [Avatar backend plan](docs/en/avatar_integration_plan.md) |

[协作规则](AGENTS.md) · [现有面试笔记](docs/zh/interview/) · [Unity setup](avatar-unity/README.md)

Keep project documents aligned in Chinese and English. Maintain current state and
acceptance criteria rather than dated progress logs; put operational commands in
component READMEs. Preserve existing interview notes and add Q&A only on request.

## License

[MIT](LICENSE).
