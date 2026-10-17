# Personal Agent Workspace

A local-first AI Agent portfolio project with a React workspace, FastAPI service
boundary, and native runtime orchestrated by LangGraph. The longer-term research
direction is an emotion-aware teaching avatar; Unity APIs remain compatible.

The current milestone is a reliable, auditable tool execution loop:

> Natural-language task → model selects tools → approval when required →
> execution → result → visible run and tool audit.

## Current scope

Implemented: workspace conversations, memory, manual/automatic handoff, optional
Codex CLI adapter, file and MCP tools, approval pause/resume, Google OAuth with
token refresh and Gmail/Calendar read/write tools, Agent Skills, Markdown hybrid
RAG, restricted demo mode, and run/usage inspection.

Next: validate real Google/MCP integrations with test accounts, finish failure-path
checks and demo materials. Further retrieval and avatar research are deferred.

## Repository layout

| Path | Responsibility |
| --- | --- |
| `server/` | FastAPI routes, services, repositories, LangGraph, runtime adapters and tools |
| `web/` | React/TypeScript workspace, conversations, settings and Run/Usage views |
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
| Future avatar integration | [Avatar 集成计划](docs/zh/avatar_integration_plan.md) | [Avatar integration plan](docs/en/avatar_integration_plan.md) |

[协作规则](AGENTS.md) · [现有面试笔记](docs/zh/interview/) · [Unity setup](avatar-unity/README.md)

Keep project documents aligned in Chinese and English. Maintain current state and
acceptance criteria rather than dated progress logs; put operational commands in
component READMEs. Preserve existing interview notes and add Q&A only on request.

## License

[MIT](LICENSE).
